# FastAPI + Globus Login

This repo includes a dev-only FastAPI application to demonstrate how Globus access tokens for specific scopes can be generated and retrieved from a Globus login button. It is not intended to be used in production. It also shows how to enforce a Globus high assurance policy within the login flow.

## Prepare Environment and Define Globus Scopes

Create virtual environment and install dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create an `.env` file with the following content:
```bash
SESSION_SECRET="unsecured-session-secret"
GLOBUS_CLIENT_ID="<your-client-id>"
GLOBUS_CLIENT_SECRET="<your-client-secret>"
GLOBUS_REDIRECT_URI="http://localhost:8000/auth/callback"
REQUESTED_SCOPES="<your-globus-scopes-(separated by a space)>"
```

For example, if you want to request the ALCF Inference Service scope:
```bash
REQUESTED_SCOPES="https://auth.globus.org/scopes/681c10cc-f684-4540-bcd7-0b4df3bc26ef/action_all"
```

If you want to request the Globus Compute scope:
```bash
REQUESTED_SCOPES="https://auth.globus.org/scopes/facd7ccc-c5f4-42aa-916b-a0e270e2c2a9/all"
```

If you want to request both scopes:
```bash
REQUESTED_SCOPES="https://auth.globus.org/scopes/681c10cc-f684-4540-bcd7-0b4df3bc26ef/action_all https://auth.globus.org/scopes/facd7ccc-c5f4-42aa-916b-a0e270e2c2a9/all"
```

## Add Globus High Assurance Policy in the Auth Flow

Once you have your Globus high assurance policy, simply add it to your `.env` file:
```bash
GLOBUS_HIGH_ASSURANCE_POLICY="<your-globus-policy>"
```

## Create Globus Portal Client

Visit [https://app.globus.org/settings/developers](https://app.globus.org/settings/developers) and follow these instructions:
* Click on "Register a portal ..."
* Select "none of the above - create a new project" and click on "Continue"
* Fill the App Registration form
    * App Name: My Dev Portal
    * Redirects: http://localhost:8000/auth/callback
    * Leave the rest of the fields to their default value
    * Click on "Register App"
    * Click on "Add Secret Client", enter a name (e.g. my-dev-portal), and click on "Generate secret"

Copy-paste the Client UUID and the secret into your `GLOBUS_CLIENT_ID` and `GLOBUS_CLIENT_SECRET` variables in your `.env` file.

## Create Globus High Assurance Policy

In the same Project space you created your Portal Client (see step above):
* Click on the "Policies" tab
* Click on "Add a Policy"
* Fill the App Registration form
    * Display Name: My High Assurance Policy
    * Description: Policy for the globus-login-portal-example project
    * **Important**: Check the box for "High Assurance"
    * Included Domains: list your allowed domains (e.g., alcf.anl.gov my-institution.gov etc ...)
        * One domain per line
    * Click on "Create Policy"

Copy-paste the Policy UUID into your `GLOBUS_HIGH_ASSURANCE_POLICY` variable in your `.env` file.

## Run Application

Run fastapi in development mode
```bash
fastapi dev main.py
```

View the application on your browser at `http://localhost:8000/`. Once authenticated, you will be able to view your Globus token. Look into the `other_tokens` field to see the access tokens generated for your requested scopes.

