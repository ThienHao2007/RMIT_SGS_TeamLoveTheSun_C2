# Submission verification

Checked on Windows using a temporary checkout copied from the clean submission folder. Generated dependencies, keys, databases, and test caches were kept out of the upload folder.

| Check | Observed result |
| --- | --- |
| `setup.bat` invoked from another working directory | Created a new virtual environment, installed dependencies, generated demo keypairs and built the UI successfully |
| UI build | Vite production build succeeded |
| UI lint | ESLint passed |
| Backend tests | 26 passed |
| `demo.py` invoked from another working directory | Real HTTP requests passed: public 200, pending 429, self-approval 403, distinct-administrator approval 200, approved result 200, policy tamper 403 |
| `run.py --port ... --no-browser` invoked from another working directory | Served built UI HTML, JavaScript asset and public API successfully on the selected port |
| `setup.sh` | Bash syntax check passed; macOS/Linux installation was not executed |
| README overview | 239 whitespace-separated words including section headings; below 300 |
| Video | H.264/AAC MP4, 1600×800, approximately 119.18 seconds, 3,668,472 bytes |

The supplied recording's audio track was silent (volume detection reported a maximum of −91 dB). The submission video therefore uses English story cards and captions; it does not contain newly recorded narration. Credential/editor scenes were replaced with opaque cards and the result was inspected through frame contact sheets. Review the complete video before public release.

Docker images were not built in this verification. Live TideCloak integration, public hosting, GitHub publication and form submission were not performed. The video records the team's existing local demo; setup and launcher portability improvements were verified separately afterward.
