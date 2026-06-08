# Staff Management — Workflow and Approval Matrix

## Objective

This document defines the complete staff management module scope for the AR Society ERP project.

## Hierarchy

Committee Members
- Chairman
- Secretary
- Treasurer

approve -> Manager

Manager approves -> Security Supervisor / Housekeeping Supervisor / Technical Staff

Security Staff / Housekeeping Staff report to their supervisor.
Technical Staff reports directly to Manager.
Gym Trainer attendance is approved by Housekeeping Supervisor.

## Staff Master

Core staff fields:
- Employee Code
- Employee Name
- Mobile Number
- Email
- Department
- Designation
- Reporting Manager
- Joining Date
- Employment Status
- Shift
- Society

Departments:
- Security
- Housekeeping
- Technical
- Gym
- Administration

Designations:
- Manager
- Security Supervisor
- Security Guard
- Housekeeping Supervisor
- Housekeeping Staff
- Technical Staff
- Gym Trainer

## Attendance Workflow

1. Staff login
2. Punch In
3. Pending Approval
4. Supervisor / Manager / Committee approval
5. Duty assignment

### Department-specific approval rules
- Security Staff -> Security Supervisor approval
- Housekeeping Staff -> Housekeeping Supervisor approval
- Gym Trainer -> Housekeeping Supervisor approval
- Technical Staff -> Manager approval
- Security Supervisor -> Manager approval
- Housekeeping Supervisor -> Manager approval
- Manager -> Committee Member approval

## Out-Punch Workflow

1. Staff Punch Out
2. Supervisor approval
3. Manager approval
4. Committee approval

## Manager Dashboard

Show:
- Pending Attendance Approvals
- Pending Punch-Out Approvals
- Pending Complaint Assignments
- Department-wise Staff Status
- Absent Staff
- Late Arrivals

## Supervisor Dashboard

### Security Supervisor
- Staff Present
- Staff Absent
- Pending Punch-In
- Pending Punch-Out
- Duty Assignment

### Housekeeping Supervisor
- Staff Present
- Staff Absent
- Pending Punch-In
- Pending Punch-Out
- Duty Assignment
- Gym Trainer Attendance

## Duty Assignment Rules

### Security
- Main Gate
- Visitor Gate
- Parking Gate
- Night Patrol

### Housekeeping
- Wing A
- Wing B
- Club House
- Garden
- Parking Area

### Technical
- Electrical
- Plumbing
- Lift Maintenance
- Generator Room

## Complaint Assignment

Manager can assign complaints to:
- Security
- Housekeeping
- Technical

Track status:
- Assigned
- In Progress
- Completed

## Implementation Notes

This document is the source of truth for the staff management module implementation.
