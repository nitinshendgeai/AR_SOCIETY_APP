# Mobile Release Readiness (Android)

Rating: PASS, FAIL, CONDITIONAL PASS, NOT VERIFIED. **No Android build was made for this review**: the work environment has no
Android SDK, and the signing secrets are (correctly) not available to it. Everything below comes from reading the project files,
the Flutter SDK source at the CI-pinned version, and CI results. A real release needs the checks marked NOT VERIFIED.

| # | Item | Status | Evidence / what is left |
|---|---|---|---|
| 1 | Application ID | PASS | `in.duxos.society` as namespace and `applicationId` (`android/app/build.gradle`) |
| 2 | App name and branding | CONDITIONAL PASS | Launcher label "DUX OS"; Play listing name is set in the Play Console. Decide the public name ("DuxOS Society"?) |
| 3 | Launcher icon | CONDITIONAL PASS | Adaptive icon XML and all mipmap densities present. Not looked at on a device |
| 4 | Splash screen | CONDITIONAL PASS | Uses the classic window background (`launch_background`). Android 12+ shows its system splash from the launcher icon instead. A themed Android 12 splash (`values-v31`) was **not** added because it cannot be build-tested here; add it in a build-verified change |
| 5 | Permissions | PASS (minimal set) | INTERNET, ACCESS_NETWORK_STATE, USE_BIOMETRIC, CAMERA (payment screenshot), POST_NOTIFICATIONS (visitor alerts). Each has a feature behind it. Must be declared in the Play Data safety form: NOT VERIFIED |
| 6 | Signing | CONDITIONAL PASS | Upload key from `key.properties` or `ANDROID_KEYSTORE_*` secrets (`build.gradle`); the AAB workflow stops if the secret is missing. Without a key the release build falls back to the debug key, which Play rejects. Whether the four repository secrets are set: NOT VERIFIED. Credentials are never in the repository (`.gitignore`, gitleaks CI) |
| 7 | Versioning | PASS | `1.0.0+1`; the AAB workflow sets the build number to the run number so every upload is higher |
| 8 | Target and minimum API | PASS | Flutter 3.47.5 (the CI-pinned version) targets and compiles against API 36, minimum API 24 (`FlutterExtension.kt`) |
| 9 | Flutter version in build workflows | PASS (this change) | `build-apk.yml` and `build-aab.yml` were on the moving `stable` channel; now pinned to 3.47.5, the version `flutter-ci.yml` analyzes and tests. Production web `mobile/Dockerfile` still uses unpinned stable: left alone, noted |
| 10 | Release build (AAB) | NOT VERIFIED | Run "Build Android App Bundle (Play Store)" in Actions with the secrets set. The Flutter web release build compiles in CI (PASS) |
| 11 | Network security | PASS | Cleartext traffic off; system trust anchors only (`network_security_config.xml`); API base URL is https |
| 12 | Backup of app data | PASS (this change, unbuilt) | `allowBackup="false"` added: the app keeps sign-in tokens in encrypted storage, which cannot be decrypted on a restored device and should not be copied off it |
| 13 | Secure session handling | PASS (existing) | Tokens in Android Keystore-backed storage; refresh and forced sign-out on server rejection; biometric lock; signed-in-devices screen |
| 14 | Deep links / App Links | FAIL (not implemented) | No intent filter. Opening `society.duxos.in` links in the app needs an `assetlinks.json` on that domain and a manifest filter: a change to the production web host, so it needs your approval |
| 15 | Push notifications | NOT VERIFIED | `androidAppId` in `push_config.dart` must be the Firebase app registered for `in.duxos.society` (`docs/ANDROID_RELEASE.md`) |
| 16 | Code shrinking (R8) | NOT VERIFIED | Disabled on purpose after a native-crash history; enabling needs keep rules tested on real devices |
| 17 | Privacy | CONDITIONAL PASS | Account and data deletion page added (#232). Privacy-policy URL and the Data safety form: NOT VERIFIED |
| 18 | Who the Android app is for | Decision needed | The signed build uses `APP_EDITION=field`: residents, tenants, security, technical and gym staff only. Admin, committee and manager roles are told to use the web app. The new Operations / Finance / People tabs therefore reach those roles on the **web app opened on a phone** until you decide to ship them an Android edition |
| 19 | Device and screen-size testing | NOT VERIFIED | Nothing was run on a device or emulator. Layouts are covered by widget tests only |
| 20 | Play listing assets | NOT VERIFIED | Screenshots, feature graphic, short and long description, content rating, closed-testing track first |

## Before the first upload (in order)
1. Set the four signing secrets (and `API_BASE_URL` variable if it differs); run the AAB workflow; install the artifact on a real phone.
2. Register the Firebase app and confirm `androidAppId`.
3. Complete Data safety, content rating, privacy policy URL, deletion URL.
4. Test on at least one small (about 360 x 640) and one large phone, at 130% font size, in English and Marathi, on a slow connection.
5. Upload to **Closed testing**, not production.
