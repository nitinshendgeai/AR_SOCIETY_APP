import calendar
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, Request
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.modules.inventory.models.inventory import (
    InventoryCategory, InventoryItem, InventoryStock, InventoryTransaction,
    InventoryIssue, InventoryReturn, Asset, AssetMaintenance, AssetAMC, AssetUsageLog,
    TransactionType, IssueStatus, AssetStatus, AssetCategory, MaintenanceStatus,
)
from app.modules.inventory.schemas.inventory import (
    CategoryCreate, ItemCreate, ItemUpdate, StockInRequest, StockAdjustRequest,
    IssueCreate, ReturnCreate, AssetCreate, AssetUpdate, AssetAssignRequest,
    MaintenanceCreate, MaintenanceCompleteRequest, AMCCreate,
)
from app.modules.inventory.repositories.inventory_repo import (
    InventoryCategoryRepo, InventoryItemRepo, InventoryStockRepo,
    InventoryTransactionRepo, InventoryIssueRepo,
    AssetRepo, AssetMaintenanceRepo, AssetAMCRepo,
)
from app.core.tenant_scope import assert_society_access, resolve_create_society_id
from app.utils.local_time import local_today, zone
from app.models.user import User
from app.models.audit_log import AuditAction
from app.services.audit_service import AuditService
from app.services.notification_service import NotificationService
from app.models.notification import NotificationType, NotificationChannel


class InventoryService:

    def __init__(self, db: Session):
        self.db        = db
        self.cat_repo  = InventoryCategoryRepo(db)
        self.item_repo = InventoryItemRepo(db)
        self.stock_repo= InventoryStockRepo(db)
        self.txn_repo  = InventoryTransactionRepo(db)
        self.issue_repo= InventoryIssueRepo(db)
        self.asset_repo= AssetRepo(db)
        self.maint_repo= AssetMaintenanceRepo(db)
        self.amc_repo  = AssetAMCRepo(db)

    # ── Helpers ───────────────────────────────────────────────────────────────
    # Role checks say what a caller may do; these say which society's data it may touch.
    # Something that belongs to another society is reported as not found, so ids can't
    # be probed. A platform admin (society_id None) may work in any society.

    @staticmethod
    def _in_scope(user: Optional[User], society_id) -> bool:
        return user is None or user.society_id is None or user.society_id == society_id

    def _scoped_or_404(self, row, user: Optional[User], what: str):
        if row is None or not self._in_scope(user, row.society_id):
            raise HTTPException(status_code=404, detail=f"{what} not found")
        return row

    def _item_or_404(self, item_id: UUID, user: Optional[User] = None) -> InventoryItem:
        return self._scoped_or_404(self.item_repo.get(item_id), user, "Inventory item")

    def _asset_or_404(self, asset_id: UUID, user: Optional[User] = None) -> Asset:
        return self._scoped_or_404(self.asset_repo.get(asset_id), user, "Asset")

    def _same_society_user(self, user_id: Optional[UUID], society_id: UUID, what: str):
        if user_id is None: return
        u = self.db.query(User).filter(User.id == user_id).first()
        if u is None or u.society_id != society_id:
            raise HTTPException(status_code=422, detail=f"{what} not found in this society")

    def _same_society_staff(self, staff_id: Optional[UUID], society_id: UUID):
        if staff_id is None: return
        from app.modules.staff.models.staff import Staff
        st = self.db.query(Staff).filter(Staff.id == staff_id).first()
        if st is None or st.society_id != society_id:
            raise HTTPException(status_code=422, detail="Staff member not found in this society")

    def _audit(self, action, entity, entity_type, user, request=None, **kw):
        AuditService.log(db=self.db, action=action, module="inventory",
                         entity_id=str(entity.id), entity_type=entity_type,
                         user=user, request=request, **kw)

    def _record_txn(self, item: InventoryItem, stock: InventoryStock,
                    txn_type: TransactionType, qty: float,
                    user: User, notes=None, ref=None, unit_cost=None) -> InventoryTransaction:
        qty_before = stock.current_quantity
        if txn_type in (TransactionType.STOCK_OUT, TransactionType.CONSUMPTION,
                        TransactionType.TRANSFER, TransactionType.ISSUE_TXN if hasattr(TransactionType, 'ISSUE_TXN') else None):
            qty_after = qty_before - qty
        else:
            qty_after = qty_before + qty

        total = float(unit_cost) * qty if unit_cost else None
        txn = InventoryTransaction(
            society_id=item.society_id, item_id=item.id,
            transaction_type=txn_type, quantity=qty,
            quantity_before=qty_before, quantity_after=qty_after,
            unit_cost=unit_cost, total_cost=total,
            reference_id=ref, notes=notes, performed_by=user.id,
        )
        self.db.add(txn)
        stock.current_quantity = qty_after
        stock.last_updated_by  = user.id
        return txn

    def _check_low_stock(self, item: InventoryItem, stock: InventoryStock, user: User):
        if stock.current_quantity <= item.minimum_stock and user:
            NotificationService.send(
                db=self.db, user_id=user.id,
                title="Low Stock Alert",
                body=f"{item.name} ({item.item_code}) is below minimum stock. Current: {stock.current_quantity} {item.unit_type.value}",
                type=NotificationType.WARNING, channel=NotificationChannel.IN_APP,
                module="inventory", entity_id=str(item.id),
            )

    # ── Category ──────────────────────────────────────────────────────────────

    def create_category(self, data: CategoryCreate, user: User) -> InventoryCategory:
        society_id = resolve_create_society_id(user, data.society_id)
        c = InventoryCategory(**{**data.model_dump(), "society_id": society_id})
        return self.cat_repo.create(c)

    def list_categories(self, society_id: UUID, user: Optional[User] = None) -> List[InventoryCategory]:
        if user is not None: assert_society_access(user, society_id)
        return self.cat_repo.get_by_society(society_id)

    # ── Inventory Items ───────────────────────────────────────────────────────

    def _with_stock(self, items: List[InventoryItem]) -> List[InventoryItem]:
        """Put each item's quantity in hand on it (``current_stock``) for the API output."""
        if not items: return items
        rows = self.db.query(InventoryStock.item_id, InventoryStock.current_quantity)\
            .filter(InventoryStock.item_id.in_([i.id for i in items])).all()
        qty = {item_id: q for item_id, q in rows}
        for i in items:
            i.current_stock = qty.get(i.id, 0)
        return items

    def create_item(self, data: ItemCreate, user: User, request=None) -> InventoryItem:
        society_id = resolve_create_society_id(user, data.society_id)
        if data.category_id is not None:
            cat = self.cat_repo.get(data.category_id)
            if cat is None or cat.society_id != society_id:
                raise HTTPException(status_code=422, detail="Category not found in this society")
        self._name_free(society_id, data.name)
        code = self.item_repo.next_item_code(society_id)
        item = InventoryItem(**{**data.model_dump(), "society_id": society_id}, item_code=code)
        self.item_repo.create(item)
        # Initialize stock record
        self.stock_repo.get_or_create(item.id, society_id)
        self._audit(AuditAction.CREATE, item, "InventoryItem", user, request,
                    new_values={"code": code, "name": data.name})
        self.db.commit()
        return self._with_stock([item])[0]

    def _name_free(self, society_id: UUID, name: str, exclude: Optional[UUID] = None) -> None:
        q = self.db.query(InventoryItem.id).filter(
            InventoryItem.society_id == society_id, InventoryItem.is_active == True,
            InventoryItem.name.ilike(name.strip()))
        if exclude:
            q = q.filter(InventoryItem.id != exclude)
        if q.first():
            raise HTTPException(status_code=409, detail=f"There is already an item called “{name.strip()}”")

    def _scope_today(self, society_id: UUID) -> date:
        from app.models.society import Society
        society = self.db.query(Society).filter(Society.id == society_id).first()
        return local_today(zone(society.timezone if society else None))

    def update_item(self, item_id: UUID, data: ItemUpdate, user: User) -> InventoryItem:
        item = self._item_or_404(item_id, user)
        changes = {k: v for k, v in data.model_dump(exclude_unset=True).items()
                   if not (k in ("name", "category", "is_active") and v is None)
                   and not (k == "name" and not (v or "").strip())}
        if "name" in changes:
            changes["name"] = changes["name"].strip()
            self._name_free(item.society_id, changes["name"], exclude=item.id)
        if changes.get("is_active") is False:
            stock = self.stock_repo.get_by_item(item.id)
            if stock and stock.current_quantity > 0:
                raise HTTPException(status_code=409, detail="There is still stock of it. Count it down to zero before retiring it.")
            if self.db.query(InventoryIssue.id).filter(
                    InventoryIssue.item_id == item.id,
                    InventoryIssue.status.in_([IssueStatus.ISSUED, IssueStatus.PARTIALLY_RETURNED])).first():
                raise HTTPException(status_code=409, detail="Some of it is still out with someone. Get it back first.")
        self.item_repo.update(item, changes)
        return self._with_stock([item])[0]

    def get_item(self, item_id: UUID, user: Optional[User] = None) -> InventoryItem:
        return self._with_stock([self._item_or_404(item_id, user)])[0]

    def list_items(self, society_id: UUID, skip=0, limit=50, user: Optional[User] = None,
                   q: Optional[str] = None, category: Optional[str] = None) -> List[InventoryItem]:
        if user is not None: assert_society_access(user, society_id)
        query = self.db.query(InventoryItem).filter(InventoryItem.society_id == society_id,
                                                    InventoryItem.is_active == True)
        if q:
            like = f"%{q.strip()}%"
            query = query.filter(or_(InventoryItem.name.ilike(like), InventoryItem.item_code.ilike(like)))
        if category:
            query = query.filter(InventoryItem.category == category)
        items = query.order_by(InventoryItem.name).offset(skip).limit(limit).all()
        return self._with_stock(items)

    def get_low_stock_items(self, society_id: UUID, user: Optional[User] = None) -> List[InventoryItem]:
        if user is not None: assert_society_access(user, society_id)
        return self._with_stock(self.item_repo.get_low_stock(society_id))

    # ── Stock operations ──────────────────────────────────────────────────────

    def stock_in(self, data: StockInRequest, user: User, request=None) -> InventoryStock:
        item  = self._item_or_404(data.item_id, user)
        stock = self.stock_repo.get_or_create(item.id, item.society_id)
        self._record_txn(item, stock, TransactionType.STOCK_IN, data.quantity, user,
                         notes=data.notes, ref=data.reference_id, unit_cost=data.unit_cost)
        self._audit(AuditAction.UPDATE, item, "InventoryItem", user, request,
                    new_values={"action": "stock_in", "qty": data.quantity,
                                "new_total": stock.current_quantity})
        self.db.commit()
        self.db.refresh(stock)
        return stock

    def stock_adjust(self, data: StockAdjustRequest, user: User, request=None) -> InventoryStock:
        if data.new_quantity < 0:
            raise HTTPException(status_code=422, detail="Quantity can't be negative")
        item  = self._item_or_404(data.item_id, user)
        stock = self.stock_repo.get_or_create(item.id, item.society_id)
        diff  = data.new_quantity - stock.current_quantity
        txn_type = TransactionType.ADJUSTMENT
        # Record as ADJUSTMENT — quantity is the diff (positive or negative)
        qty_before = stock.current_quantity
        txn = InventoryTransaction(
            society_id=item.society_id, item_id=item.id,
            transaction_type=txn_type, quantity=abs(diff),
            quantity_before=qty_before, quantity_after=data.new_quantity,
            notes=data.notes, performed_by=user.id,
        )
        self.db.add(txn)
        stock.current_quantity = data.new_quantity
        stock.last_updated_by  = user.id
        self._check_low_stock(item, stock, user)
        self._audit(AuditAction.UPDATE, item, "InventoryItem", user, request,
                    new_values={"action": "adjusted", "from": qty_before, "to": data.new_quantity, "why": data.notes})
        self.db.commit()
        self.db.refresh(stock)
        return stock

    def get_stock(self, item_id: UUID, user: Optional[User] = None) -> InventoryStock:
        self._item_or_404(item_id, user)
        s = self.stock_repo.get_by_item(item_id)
        if not s: raise HTTPException(status_code=404, detail="Stock record not found")
        return s

    def get_transactions(self, item_id: UUID, skip=0, limit=50, user: Optional[User] = None) -> List[InventoryTransaction]:
        self._item_or_404(item_id, user)
        return self.txn_repo.get_by_item(item_id, skip, limit)

    # ── Issue / Return ────────────────────────────────────────────────────────

    def _same_society_link(self, model_path: str, row_id: Optional[UUID], society_id: UUID, what: str):
        if row_id is None: return
        import importlib
        mod, cls = model_path.rsplit(".", 1)
        model = getattr(importlib.import_module(mod), cls)
        row = self.db.query(model).filter(model.id == row_id).first()
        if row is None or getattr(row, "society_id", None) != society_id:
            raise HTTPException(status_code=422, detail=f"{what} not found in this society")

    def issue_item(self, data: IssueCreate, user: User, request=None) -> InventoryIssue:
        item  = self._item_or_404(data.item_id, user)
        if not item.is_active:
            raise HTTPException(status_code=409, detail=f"{item.name} has been retired and can't be issued")
        if data.issued_to_user is None and data.issued_to_staff is None:
            raise HTTPException(status_code=422, detail="Say who it is being given to")
        self._same_society_user(data.issued_to_user, item.society_id, "User")
        self._same_society_staff(data.issued_to_staff, item.society_id)
        self._same_society_link("app.modules.complaint.models.complaint.Complaint", data.complaint_id, item.society_id, "Complaint")
        if data.expected_return_date is not None and not data.consumed \
                and data.expected_return_date < self._scope_today(item.society_id):
            raise HTTPException(status_code=422, detail="The return date can't be in the past")
        stock = self.stock_repo.get_or_create(item.id, item.society_id)

        if stock.current_quantity < data.quantity_issued:
            raise HTTPException(status_code=409,
                detail=f"Insufficient stock. Available: {stock.current_quantity} {item.unit_type.value}, Requested: {data.quantity_issued}")

        # Deduct stock
        self._record_txn(item, stock,
                         TransactionType.CONSUMPTION if data.consumed else TransactionType.STOCK_OUT,
                         data.quantity_issued, user,
                         notes=data.purpose, ref=str(data.issued_to_user or data.issued_to_staff or ""))

        values = data.model_dump(exclude={"consumed", "society_id"})
        if data.consumed:
            values["expected_return_date"] = None
        issue = InventoryIssue(**values, society_id=item.society_id, issued_by=user.id,
                               status=IssueStatus.CONSUMED if data.consumed else IssueStatus.ISSUED)
        self.db.add(issue)
        self.db.flush()

        self._check_low_stock(item, stock, user)
        self._audit(AuditAction.UPDATE, item, "InventoryItem", user, request,
                    new_values={"action": "issued", "qty": data.quantity_issued})
        self.db.commit()
        self.db.refresh(issue)
        return issue

    def return_item(self, data: ReturnCreate, user: User, request=None) -> InventoryIssue:
        issue = self._scoped_or_404(self.issue_repo.get(data.issue_id), user, "Issue record")
        if issue.status == IssueStatus.RETURNED:
            raise HTTPException(status_code=409, detail="Item already fully returned")
        if issue.status == IssueStatus.CONSUMED:
            raise HTTPException(status_code=409, detail="That was used up, so there is nothing to return")

        remaining_to_return = issue.quantity_issued - issue.quantity_returned
        if data.quantity > remaining_to_return:
            raise HTTPException(status_code=409,
                detail=f"Cannot return {data.quantity}. Max returnable: {remaining_to_return}")

        item  = self._item_or_404(issue.item_id, user)
        stock = self.stock_repo.get_or_create(item.id, item.society_id)
        # A damaged or lost item is closed off on the issue but doesn't go back on the shelf.
        usable = (data.condition or "good").strip().lower() not in ("damaged", "lost")
        if usable:
            self._record_txn(item, stock, TransactionType.RETURN, data.quantity, user, notes=data.notes)

        ret = InventoryReturn(
            issue_id=issue.id, society_id=issue.society_id,
            quantity=data.quantity, condition=data.condition,
            returned_by=user.id, received_by=user.id, notes=data.notes,
        )
        self.db.add(ret)

        issue.quantity_returned += data.quantity
        issue.actual_return_date = date.today()
        if issue.quantity_returned >= issue.quantity_issued:
            issue.status = IssueStatus.RETURNED
        else:
            issue.status = IssueStatus.PARTIALLY_RETURNED

        self._audit(AuditAction.UPDATE, item, "InventoryItem", user, request,
                    new_values={"action": "returned", "qty": data.quantity, "usable": usable})
        self.db.commit()
        self.db.refresh(issue)
        return issue

    def get_issues(self, society_id: UUID, skip=0, limit=50, user: Optional[User] = None,
                   status: Optional[str] = None, item_id: Optional[UUID] = None) -> List[InventoryIssue]:
        """Issues, newest first. ``status`` may be ``open`` (still out), ``overdue`` or any issue status."""
        if user is not None: assert_society_access(user, society_id)
        q = self.db.query(InventoryIssue).filter(InventoryIssue.society_id == society_id,
                                                 InventoryIssue.is_active == True)
        if item_id:
            q = q.filter(InventoryIssue.item_id == item_id)
        out_now = [IssueStatus.ISSUED, IssueStatus.PARTIALLY_RETURNED]
        if status == "open":
            q = q.filter(InventoryIssue.status.in_(out_now))
        elif status == "overdue":
            q = q.filter(InventoryIssue.status.in_(out_now), InventoryIssue.expected_return_date != None,
                         InventoryIssue.expected_return_date < self._scope_today(society_id))
        elif status:
            q = q.filter(InventoryIssue.status == status)
        return q.order_by(InventoryIssue.created_at.desc()).offset(skip).limit(limit).all()

    def issue_rows(self, issues: List[InventoryIssue]) -> List[dict]:
        """Issues with the names a screen shows: the item, who has it, who gave it, and what is still out."""
        from app.modules.staff.models.staff import Staff
        from app.modules.inventory.schemas.inventory import IssueOut
        staff_ids = [i.issued_to_staff for i in issues if i.issued_to_staff]
        staff = {st.id: st for st in self.db.query(Staff).filter(Staff.id.in_(staff_ids)).all()} if staff_ids else {}
        today = self._scope_today(issues[0].society_id) if issues else None
        rows = []
        for i in issues:
            d = IssueOut.model_validate(i).model_dump(mode="json")
            out = max(i.quantity_issued - i.quantity_returned, 0) if i.status != IssueStatus.CONSUMED else 0
            st = staff.get(i.issued_to_staff)
            d.update({
                "item_name": i.item.name if i.item else None,
                "item_code": i.item.item_code if i.item else None,
                "unit": i.item.unit_type.value if i.item else None,
                "issued_to_staff": str(i.issued_to_staff) if i.issued_to_staff else None,
                "issued_to_name": (st.full_name if st else (i.issued_to.full_name if i.issued_to else None)),
                "issued_by_name": i.issuer.full_name if i.issuer else None,
                "outstanding": out,
                "overdue": bool(out and i.expected_return_date and today and i.expected_return_date < today),
                "notes": i.notes,
            })
            rows.append(d)
        return rows

    def transaction_rows(self, txns: List[InventoryTransaction]) -> List[dict]:
        from app.modules.inventory.schemas.inventory import TransactionOut
        rows = []
        for t in txns:
            d = TransactionOut.model_validate(t).model_dump(mode="json")
            d["performed_by_name"] = t.performer.full_name if t.performer else None
            rows.append(d)
        return rows

    def stores_summary(self, society_id: UUID, user: Optional[User] = None) -> dict:
        """Numbers for the top of the Stores screen."""
        if user is not None: assert_society_access(user, society_id)
        items = self.db.query(InventoryItem).filter(InventoryItem.society_id == society_id,
                                                    InventoryItem.is_active == True).all()
        qty = dict(self.db.query(InventoryStock.item_id, InventoryStock.current_quantity)
                   .filter(InventoryStock.society_id == society_id).all())
        value = 0.0
        low = out = 0
        for i in items:
            q = qty.get(i.id, 0) or 0
            if q <= 0: out += 1
            if q <= (i.minimum_stock or 0): low += 1
            if i.unit_cost is not None: value += float(i.unit_cost) * q
        open_issues = self.get_issues(society_id, 0, 1000, None, status="open")
        overdue = [i for i in open_issues if i.expected_return_date and i.expected_return_date < self._scope_today(society_id)]
        return {"items": len(items), "low_stock": low, "out_of_stock": out,
                "stock_value": round(value, 2), "out_with_people": len(open_issues), "overdue_returns": len(overdue)}

    # ── Asset register ────────────────────────────────────────────────────────

    @staticmethod
    def _add_months(d: date, months: int) -> date:
        m = d.month - 1 + months
        year, month = d.year + m // 12, m % 12 + 1
        return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))

    def _next_service(self, interval: Optional[int], last: Optional[date], bought: Optional[date]) -> Optional[date]:
        """When the next service falls: the interval after the last one, else after purchase."""
        base = last or bought
        return self._add_months(base, interval) if interval and base else None

    def create_asset(self, data: AssetCreate, user: User, request=None) -> Asset:
        society_id = resolve_create_society_id(user, data.society_id)
        values = {**data.model_dump(), "society_id": society_id}
        if values.get("next_service_due") is None:
            values["next_service_due"] = self._next_service(
                data.service_interval_months, data.last_serviced_on, data.purchase_date)
        code  = self.asset_repo.next_asset_code(society_id)
        asset = Asset(**values, asset_code=code)
        self.asset_repo.create(asset)
        # Initial usage log
        log = AssetUsageLog(asset_id=asset.id, society_id=asset.society_id,
                            logged_by=user.id, action="REGISTERED",
                            notes=f"Asset registered by {user.email}")
        self.db.add(log)
        self._audit(AuditAction.CREATE, asset, "Asset", user, request,
                    new_values={"code": code, "name": data.name, "category": data.asset_category.value})
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def update_asset(self, asset_id: UUID, data: AssetUpdate, user: User, request=None) -> Asset:
        asset = self._asset_or_404(asset_id, user)
        changes = data.model_dump(exclude_unset=True)
        # These can't be blank; everything else can be cleared by sending null.
        for required in ("name", "asset_category", "status"):
            if required in changes and changes[required] in (None, ""):
                changes.pop(required)
        if "name" in changes:
            changes["name"] = changes["name"].strip()
            if not changes["name"]:
                raise HTTPException(status_code=422, detail="Name is required")
        old_status = asset.status
        for key, value in changes.items():
            setattr(asset, key, value)
        # A new interval re-works the due date unless one was given with it.
        if ("service_interval_months" in changes or "last_serviced_on" in changes) and "next_service_due" not in changes:
            asset.next_service_due = self._next_service(
                asset.service_interval_months, asset.last_serviced_on, asset.purchase_date)
        if asset.status != old_status:
            self.db.add(AssetUsageLog(asset_id=asset.id, society_id=asset.society_id, logged_by=user.id,
                                      action="STATUS_CHANGED",
                                      notes=f"{old_status.value} to {asset.status.value}"))
        self._audit(AuditAction.UPDATE, asset, "Asset", user, request,
                    new_values={k: str(v) for k, v in changes.items()})
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def get_asset(self, asset_id: UUID, user: Optional[User] = None) -> Asset:
        return self._asset_or_404(asset_id, user)

    def list_assets(self, society_id: UUID, skip=0, limit=50, user: Optional[User] = None,
                    q: Optional[str] = None, category: Optional[str] = None,
                    status: Optional[str] = None, due: bool = False) -> List[Asset]:
        if user is not None: assert_society_access(user, society_id)
        query = self.db.query(Asset).filter(Asset.society_id == society_id, Asset.is_active == True)
        if q:
            like = f"%{q.strip()}%"
            query = query.filter(or_(Asset.name.ilike(like), Asset.asset_code.ilike(like),
                                     Asset.location.ilike(like), Asset.serial_number.ilike(like)))
        if category: query = query.filter(Asset.asset_category == category)
        if status:   query = query.filter(Asset.status == status)
        if due:
            soon = date.today() + timedelta(days=30)
            query = query.filter(Asset.status.in_([AssetStatus.ACTIVE, AssetStatus.UNDER_MAINTENANCE]),
                                 Asset.next_service_due != None, Asset.next_service_due <= soon)\
                         .order_by(Asset.next_service_due)
        else:
            query = query.order_by(Asset.asset_code)
        return query.offset(skip).limit(limit).all()

    def asset_summary(self, society_id: UUID, user: Optional[User] = None) -> dict:
        if user is not None: assert_society_access(user, society_id)
        today, soon = date.today(), date.today() + timedelta(days=30)
        rows = self.db.query(Asset).filter(Asset.society_id == society_id, Asset.is_active == True).all()
        counted = [a for a in rows if a.status in (AssetStatus.ACTIVE, AssetStatus.UNDER_MAINTENANCE)]
        by_category: dict = {}
        for a in rows:
            by_category[a.asset_category.value] = by_category.get(a.asset_category.value, 0) + 1
        amc_expiring = self.db.query(func.count(AssetAMC.id)).filter(
            AssetAMC.society_id == society_id, AssetAMC.is_active == True,
            AssetAMC.end_date >= today, AssetAMC.end_date <= soon).scalar() or 0
        return {
            "total": len(rows),
            "active": sum(1 for a in rows if a.status == AssetStatus.ACTIVE),
            "under_maintenance": sum(1 for a in rows if a.status == AssetStatus.UNDER_MAINTENANCE),
            "retired": sum(1 for a in rows if a.status in (AssetStatus.RETIRED, AssetStatus.DISPOSED, AssetStatus.LOST)),
            "total_purchase_cost": sum((a.purchase_cost or Decimal(0)) for a in counted) or Decimal(0),
            "warranty_expiring": sum(1 for a in counted if a.warranty_expiry and today <= a.warranty_expiry <= soon),
            "warranty_expired": sum(1 for a in counted if a.warranty_expiry and a.warranty_expiry < today),
            "service_overdue": sum(1 for a in counted if a.next_service_due and a.next_service_due < today),
            "service_due_soon": sum(1 for a in counted if a.next_service_due and today <= a.next_service_due <= soon),
            "amc_expiring": amc_expiring,
            "by_category": by_category,
        }

    def assign_asset(self, asset_id: UUID, data: AssetAssignRequest,
                     user: User, request=None) -> Asset:
        asset = self._asset_or_404(asset_id, user)
        self._same_society_user(data.assigned_to_user, asset.society_id, "User")
        self._same_society_staff(data.assigned_to_staff, asset.society_id)
        asset.assigned_to_user  = data.assigned_to_user
        asset.assigned_to_staff = data.assigned_to_staff
        asset.assigned_at = datetime.utcnow()
        log = AssetUsageLog(asset_id=asset.id, society_id=asset.society_id,
                            logged_by=user.id, action="ASSIGNED",
                            notes=data.notes or f"Assigned by {user.email}")
        self.db.add(log)
        self._audit(AuditAction.UPDATE, asset, "Asset", user, request,
                    new_values={"action": "assigned", "to": str(data.assigned_to_user or data.assigned_to_staff)})
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def get_expiring_warranties(self, society_id: UUID, user: Optional[User] = None) -> List[Asset]:
        if user is not None: assert_society_access(user, society_id)
        return self.asset_repo.get_expiring_warranty(society_id)

    def asset_history(self, asset_id: UUID, user: Optional[User] = None) -> dict:
        asset = self._asset_or_404(asset_id, user)
        from app.modules.vendor.models.vendor import AMCContract, WorkOrder
        maintenance = self.db.query(AssetMaintenance).filter(
            AssetMaintenance.asset_id == asset.id, AssetMaintenance.is_active == True)\
            .order_by(AssetMaintenance.scheduled_date.desc()).all()
        contracts = self.db.query(AMCContract).filter(
            AMCContract.asset_id == asset.id, AMCContract.society_id == asset.society_id,
            AMCContract.is_active == True).order_by(AMCContract.end_date.desc()).all()
        work_orders = self.db.query(WorkOrder).filter(
            WorkOrder.asset_id == asset.id, WorkOrder.society_id == asset.society_id,
            WorkOrder.is_active == True).order_by(WorkOrder.created_at.desc()).all()
        log = self.db.query(AssetUsageLog).filter(AssetUsageLog.asset_id == asset.id)\
            .order_by(AssetUsageLog.created_at.desc()).limit(50).all()
        total = sum((m.cost or Decimal(0)) for m in maintenance if m.status == MaintenanceStatus.COMPLETED)
        return {
            "asset": asset,
            "maintenance": maintenance,
            "amc": self.amc_repo.get_by_asset(asset.id),
            "contracts": [{"id": c.id, "contract_number": c.contract_number, "contract_name": c.contract_name,
                           "status": c.status.value, "start_date": c.start_date, "end_date": c.end_date,
                           "annual_value": c.annual_value} for c in contracts],
            "work_orders": [{"id": w.id, "wo_number": w.wo_number, "title": w.title, "status": w.status.value,
                             "estimated_cost": w.estimated_cost} for w in work_orders],
            "log": log,
            "total_service_cost": total or Decimal(0),
        }

    # ── Maintenance ───────────────────────────────────────────────────────────

    def schedule_maintenance(self, data: MaintenanceCreate,
                              user: User, request=None) -> AssetMaintenance:
        asset = self._asset_or_404(data.asset_id, user)
        if asset.status in (AssetStatus.DISPOSED, AssetStatus.LOST):
            raise HTTPException(status_code=409, detail="This asset is no longer with the society")
        values = {**data.model_dump(), "society_id": asset.society_id}
        maint = AssetMaintenance(**values, performed_by=user.id)
        self.db.add(maint)
        self.db.flush()
        self._audit(AuditAction.CREATE, maint, "AssetMaintenance", user, request,
                    new_values={"type": data.maintenance_type.value, "date": str(data.scheduled_date)})
        self.db.commit()
        self.db.refresh(maint)
        return maint

    def _maint_or_404(self, maint_id: UUID, user: Optional[User]) -> AssetMaintenance:
        return self._scoped_or_404(self.maint_repo.get(maint_id), user, "Maintenance record")

    def complete_maintenance(self, maint_id: UUID,
                              data: MaintenanceCompleteRequest,
                              user: User, request=None) -> AssetMaintenance:
        maint = self._maint_or_404(maint_id, user)
        if maint.status == MaintenanceStatus.COMPLETED:
            raise HTTPException(status_code=409, detail="Maintenance already completed")
        if maint.status == MaintenanceStatus.CANCELLED:
            raise HTTPException(status_code=409, detail="This service was cancelled")
        done_on = data.completed_date or date.today()
        if done_on > date.today():
            raise HTTPException(status_code=422, detail="The service date can't be in the future")

        # The asset's own schedule moves on: last serviced, next due (the date given, else the interval).
        # Checked before anything is changed.
        asset = self._asset_or_404(maint.asset_id, user)
        moves_schedule = asset.last_serviced_on is None or done_on >= asset.last_serviced_on
        nxt = None
        if moves_schedule:
            nxt = data.next_due_date or self._next_service(asset.service_interval_months, done_on, None)
            if nxt is not None and nxt <= done_on:
                raise HTTPException(status_code=422, detail="The next service must be after this one")

        maint.status         = MaintenanceStatus.COMPLETED
        maint.completed_date = done_on
        maint.findings       = data.findings
        if data.cost is not None: maint.cost = data.cost
        if data.vendor_name: maint.vendor_name = data.vendor_name
        if moves_schedule:
            asset.last_serviced_on = done_on
            asset.next_service_due = nxt
            maint.next_due_date    = nxt
        if asset.status == AssetStatus.UNDER_MAINTENANCE:
            asset.status = AssetStatus.ACTIVE

        log = AssetUsageLog(asset_id=maint.asset_id, society_id=maint.society_id,
                            logged_by=user.id, action="MAINTENANCE_COMPLETED",
                            notes=data.findings, cost=maint.cost)
        self.db.add(log)
        self._audit(AuditAction.UPDATE, maint, "AssetMaintenance", user, request,
                    new_values={"status": "completed", "date": str(done_on)})
        self.db.commit()
        self.db.refresh(maint)
        return maint

    def cancel_maintenance(self, maint_id: UUID, user: User, request=None) -> AssetMaintenance:
        maint = self._maint_or_404(maint_id, user)
        if maint.status in (MaintenanceStatus.COMPLETED, MaintenanceStatus.CANCELLED):
            raise HTTPException(status_code=409, detail=f"Maintenance is already {maint.status.value}")
        maint.status = MaintenanceStatus.CANCELLED
        self._audit(AuditAction.UPDATE, maint, "AssetMaintenance", user, request,
                    new_values={"status": "cancelled"})
        self.db.commit()
        self.db.refresh(maint)
        return maint

    def list_maintenance(self, asset_id: UUID, skip=0, limit=20, user: Optional[User] = None) -> List[AssetMaintenance]:
        self._asset_or_404(asset_id, user)
        return self.maint_repo.get_by_asset(asset_id, skip, limit)

    def get_scheduled_maintenance(self, society_id: UUID, user: Optional[User] = None) -> List[AssetMaintenance]:
        if user is not None: assert_society_access(user, society_id)
        return self.maint_repo.get_scheduled(society_id)

    # ── AMC ───────────────────────────────────────────────────────────────────

    def add_amc(self, data: AMCCreate, user: User, request=None) -> AssetAMC:
        asset = self._asset_or_404(data.asset_id, user)
        amc = AssetAMC(**{**data.model_dump(), "society_id": asset.society_id})
        self.db.add(amc)
        self.db.flush()
        self._audit(AuditAction.CREATE, amc, "AssetAMC", user, request,
                    new_values={"vendor": data.vendor_name, "end": str(data.end_date)})
        self.db.commit()
        self.db.refresh(amc)
        return amc

    def get_amc(self, asset_id: UUID, user: Optional[User] = None) -> List[AssetAMC]:
        self._asset_or_404(asset_id, user)
        return self.amc_repo.get_by_asset(asset_id)

    def get_expiring_amc(self, society_id: UUID, user: Optional[User] = None) -> List[AssetAMC]:
        if user is not None: assert_society_access(user, society_id)
        return self.amc_repo.get_expiring(society_id)
