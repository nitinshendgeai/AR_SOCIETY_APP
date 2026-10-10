# User help guide

`DUX_OS_Help_Guide.html` is the guide people read (it has a role filter and search); `DUX_OS_Help_Guide.pdf` is the same
guide for printing or sharing. The app opens it from **Help** (phone: More → Help; computer: account menu → Help), at
the part written for the signed-in person's role (`?role=resident|guard|staff|manager|committee`).

The web build can only see `mobile/`, so the app serves a **copy** from `mobile/web/help/` at `/help/`. When you change the
guide, change it here and copy both files:

```
cp docs/user-guide/DUX_OS_Help_Guide.* mobile/web/help/
```

`mobile/test/help_launcher_test.dart` fails when the two copies differ. To rebuild the PDF, print the HTML to A4 with
background graphics in Chromium (the page has its own print layout).
