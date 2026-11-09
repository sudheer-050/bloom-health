# Bloom: local accounts, portable backups and optional photo AI

## Open Bloom

Install Python 3.10 or newer, extract the project ZIP, then double-click **Open Bloom.cmd**. Visit **http://localhost:4317** and keep the server window open while using Bloom. Alternatively run `python server.py` from this folder. Use the same browser and address each time. Do not use a static HTTP server for the photo AI feature.

Choose **Continue as guest** to use Bloom without an email, password or login. Meals, water, activities, weights and goals save automatically in this browser. Choose Continue as guest again when returning to reopen the same journal. Guest mode is shared by people using this browser and is not password-protected. Clearing browser data removes it, so download a guest JSON backup using **Backup** or **Backup & transfer** when needed. On another device, open an empty guest journal and import that JSON backup. Guest files are not encrypted.

Alternatively, create an account with your name, an email label and a password of at least 12 characters. The email is a local identifier; Bloom does not send verification emails. Each account has its own encrypted journal, separate from the guest journal. Accounts and passwords are not sent to the AI provider. Creating an account does not automatically move guest data; choose Review & move journal in the new empty account when you are ready.

## Keep data local and take it elsewhere

1. Sign in and choose **Backup**, or **Backup & transfer → Download encrypted backup**.
2. Save the `.bloom` file somewhere safe. Copy the latest file to another device using your preferred transfer method.
3. Open Bloom on that device. On the sign-in page, choose **Restore an encrypted backup**.
4. Select the file and enter the password used when it was created.
5. Review the backup contents, then choose **Restore journal and sign in**.

The backup contains the profile, goals, food entries, ingredient portions and nutrient estimates, water, activities and weights for one account. It does not include photos or AI keys. Email and backup metadata are visible; the journal contents are encrypted.

Backups are snapshots. There is no automatic syncing or merging across devices. Restoring over an existing copy requires confirmation and replaces that copy; first back up anything newer you want to keep. Another account with the same email but a different identity must be restored in a different browser profile.

**Keep your password. There is no password reset or recovery service.** Without the password, the encrypted data cannot be unlocked. Clearing browser storage removes the local accounts; retain a backup outside the browser. Refreshing or closing Bloom locks the account. Use **Lock** when you finish.

The original v1 journal is preserved until you explicitly choose **Review & move journal** in an empty account. Bloom encrypts and saves it first, then removes the old unprotected copy. Old JSON exports can also be imported into an empty account using **Backup & transfer**.

## Photo meals with online AI

1. Open **Photo meal** and choose a JPEG, PNG or WebP photo, or use the camera.
2. Choose **Connect AI** and enter your OpenAI API key in the app, not in chat. This key stays in memory for the current unlocked session; it is not saved or backed up. Developers can instead configure `OPENAI_API_KEY` in the server environment. `BLOOM_AI_MODEL` optionally overrides the default `gpt-4.1-mini` model.
3. Press **Analyze photo with AI** to send only the selected resized photo to OpenAI through the local server. This uses the OpenAI API and may incur charges. It does not send your journal, email, password or account data. No cloud request occurs just from choosing a photo.
4. Review every food and its estimated portion. Use **Edit**, change grams, remove incorrect foods, or **Add missing food or ingredient**. Include oils and sauces yourself when the photo cannot reveal them.
5. Choose a meal name, meal type and journal date. Press **Log meal as consumed**.

The app calculates totals from the reviewed portions and the per-100g nutrition values. It adds the meal to the food journal, daily totals and Meals consumed in Activity. Expand **Vitamins, minerals & more** or choose **View items** on a logged meal for details. Photos are held in memory only and discarded when locking or logging; the local server does not save them to disk. The selected photo is processed by OpenAI when you request analysis; provider data handling still applies.

Without an API key, online recognition is unavailable. The rest of Bloom works locally. Live recognition accuracy must be checked with real meal photos after connecting an API key.

## Completely local meal entry

Developers can optionally connect a model trained with Bloom's ML pipeline. See [ML-PROJECT.md](ML-PROJECT.md) for training and `--model-dir` startup. **Photo meal → Local food model → Check model** reports availability; **Recognize food locally** proposes a dominant food for review. It does not calculate nutrients from the image: confirm the label, enter grams and label/recipe values, then log the meal. Manual entry below remains available without a model.

After reviewing a local prediction, **Export reviewed training example** explicitly saves a file containing that photo and its corrected label. This is separate from journal backups and is intended only for deliberate training-data collection. Photos are otherwise not saved. The logged item retains model provenance without its photo. No automatic retraining happens.

Skip Analyze and choose **Add missing food or ingredient**. Type a starter food name to fill generic estimates, or enter your own food label/recipe values per 100 grams. Enter the portion in grams. Vitamins and minerals are optional; blank fields remain unknown. No AI or internet connection is needed for this flow.

The small built-in food list is a starter reference, not a comprehensive verified nutrient database. Actual varieties, brands and recipes differ. It cannot infer nutrients for an arbitrary custom food name without label or recipe values. AI suggestions and photo portions are also estimates. A photo cannot measure hidden oil, exact weight, or micronutrient content. **—** means unknown; **≥** means the displayed amount covers only known contributions. Totals are not an assessment of overall health or personalized dietary advice.

## Development and checks

- `dist/`: HTML, CSS and browser JavaScript. No package install or frontend build is required.
- `server.py`: loopback-only static server and optional OpenAI Responses API bridge, using Python's standard library.
- `node check-vault.cjs`: encryption, password rejection, tampering, account isolation, storage failures and date calculations.
- `node check-nutrition.cjs`: portion math, missing-data coverage and ingredient preservation in backups.
- `python -m unittest test_server.py`: provider request/response handling and local endpoint protections using mocked AI responses.

Accounts use Web Crypto PBKDF2-SHA-256 with 600,000 iterations and a random salt, then AES-256-GCM with a fresh random IV per save. Encryption keys stay in memory, are non-extractable and are not persisted. Recent Chrome, Edge, Firefox or Safari with Web Crypto and Web Locks is required. This implementation has automated checks; it has not undergone an independent security audit. Do not expose this local development server publicly.
