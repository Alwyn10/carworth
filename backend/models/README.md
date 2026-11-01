# Models folder

`python -m app.train` writes two files here:

- `carworth.joblib`: the trained model, loaded by the server (ignored by git, because it is large and can be rebuilt).
- `metrics.json`: how the models compared and how accurate the chosen one is (safe to commit and quote in the README).

Restart the server after training so it loads the new model.
