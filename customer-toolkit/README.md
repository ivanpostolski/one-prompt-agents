# Customer Deployment Toolkit

This toolkit contains everything you need to deploy your application to your dedicated AWS instance.

## Step-by-Step Guide

### 1. Initial Setup (Do this once)

Your administrator should have provided you with two pieces of information:
*   Your personal API Key (e.g., `cust_...`)
*   The API Endpoint URL (e.g., `https://...`)

**a. Create your `config.json` file:**

Make a copy of `config.json.template` and name it `config.json`.

```bash
cp config.json.template config.json
```

Now, edit `config.json` with a text editor and paste in the values you were given.

**b. Install Python dependencies:**

This toolkit uses a Python script for deployments. Install its dependencies by running:

```bash
pip install -r requirements.txt
```

### 2. Add Your Application Code

Place your application files inside the `src/` directory.

*   **Dependencies**: Add your Python dependencies to `src/requirements.txt`. The deployment process will automatically install these for you.
*   **Application Logic**: Write your main application code in the `src/` directory.

### 3. Configure Application Startup (Optional)

You can edit `scripts/start_app.sh` and `scripts/stop_app.sh` to control how your application is started and stopped. For example, to start a Python web server, you might add this to `start_app.sh`:

```bash
nohup python3 /var/www/app/your_main_file.py > /tmp/app.log 2>&1 &
```

### 4. Deploy!

Whenever you want to deploy a new version of your code, simply run the `deploy.py` script from your terminal:

```bash
python3 deploy.py
```

The script will handle authentication, package your code, upload it, and start the deployment. You will receive an email confirming the success or failure of the deployment shortly. 