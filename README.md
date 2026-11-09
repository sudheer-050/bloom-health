# Bloom

A local personal health journal with separate encrypted accounts, portable backups, and optional online AI photo meals.

Bloom also includes a trainable food classification project: data preparation, a classical baseline, ResNet18 training, evaluation reports, local inference and reviewed training-example exports. Start with [ML-PROJECT.md](ML-PROJECT.md). A real-food model still needs to be trained; synthetic verification models are blocked from use in the app.

Users can choose **Continue as guest** without logging in. Guest entries save in the current browser and can be exported as a JSON backup. Password-protected accounts remain optional.

The new product homepage introduces Bloom before account access. Choose **Start your journey** to create an account, **Sign in** for an existing local account, or **Try as a guest** for the local guest journal.

Double-click **Open Bloom.cmd**, then visit **http://localhost:4317**. Python 3.10 or newer is required. Keep the server window open while using the app.

To share, send the latest application ZIP and ask your friend to extract it first. The sharing package includes `START-HERE.txt` and `Bloom-Complete-Guide.pdf`. Each browser keeps its own journal; your localhost address is not a public sharing link.

See [USER-GUIDE.md](USER-GUIDE.md) for account creation, backup/restore on another device, connecting photo AI, manual offline meals and development checks.

Online photo recognition needs an OpenAI API key entered in **Photo meal → Connect AI**. Accounts and journals stay local; only the selected photo is sent when you request analysis. Nutrition and portion values are estimates, and users review them before logging a meal.
