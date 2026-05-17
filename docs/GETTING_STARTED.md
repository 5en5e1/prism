# Getting Started with DOM Patch Assistant

Welcome! This guide will walk you through setting up and using the DOM Patch Assistant—an AI-powered Chrome extension that lets you modify any webpage using natural language commands.

## 📋 What You'll Learn

By the end of this guide, you'll be able to:
- Set up the backend API server
- Install and configure the Chrome extension
- Make your first webpage modifications using natural language
- Understand how the system works and troubleshoot common issues

**Estimated Time:** 15-20 minutes

---

## ✅ Prerequisites

Before you begin, make sure you have the following installed:

### Required

- **Python 3.11 or higher** - [Download Python](https://www.python.org/downloads/)
  - Verify: `python --version` or `python3 --version`
- **Poetry** - Python dependency manager
  - Install: `curl -sSL https://install.python-poetry.org | python3 -`
  - Verify: `poetry --version`
- **OpenAI API Key** - [Get your API key](https://platform.openai.com/api-keys)
  - You'll need an account with available credits
- **Chrome or Chromium Browser** - [Download Chrome](https://www.google.com/chrome/)
- **Git** - For cloning the repository
  - Verify: `git --version`

### Optional

- **Node.js 18+** - Only needed if you plan to modify the extension
  - [Download Node.js](https://nodejs.org/)

---

## 🏗️ Project Overview

The DOM Patch Assistant consists of two main components that work together:

### 1. Backend API (FastAPI + Python)
- Processes webpage HTML and user commands
- Communicates with OpenAI's GPT-4o model
- Generates safe, validated DOM manipulation patches
- Runs locally on `http://localhost:8000`

### 2. Chrome Extension (Manifest V3)
- Captures webpage HTML
- Provides a user interface for commands
- Applies DOM patches to the page
- Caches changes for automatic reapplication

**How They Work Together:**
```
User Command → Extension → Backend API → OpenAI → Backend → Extension → Modified Page
```

---

## 🚀 Backend Setup

### Step 1: Clone the Repository

```bash
# Clone the repository
git clone https://github.com/yourusername/dom-patch-assistant.git
cd dom-patch-assistant
```

### Step 2: Navigate to Backend Directory

```bash
cd backend
```

### Step 3: Install Dependencies with Poetry

Poetry will create a virtual environment and install all required packages:

```bash
# Install dependencies
poetry install
```

This will install:
- FastAPI (web framework)
- OpenAI Python SDK
- Pydantic (data validation)
- BeautifulSoup4 (HTML parsing)
- And other required packages

**💡 Tip:** If you prefer using pip instead of Poetry, you can use:
```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment Variables

Create your environment configuration file:

```bash
# Copy the example environment file
cp .env.example .env
```

Now edit the `.env` file with your favorite text editor:

```bash
# Using nano
nano .env

# Or using vim
vim .env

# Or using VS Code
code .env
```

### Step 5: Add Your OpenAI API Key

In the `.env` file, find the line with `OPENAI_API_KEY` and replace the placeholder with your actual API key:

```env
# Before
OPENAI_API_KEY=sk-your-api-key-here

# After (example)
OPENAI_API_KEY=sk-proj-abc123xyz789...
```

**Important Configuration Options:**

```env
# Model to use (gpt-4o is recommended)
OPENAI_DEFAULT_MODEL=gpt-4o

# Timeout for API calls (in seconds)
OPENAI_TIMEOUT_S=600

# Maximum HTML size to process (5MB default)
MAX_INPUT_HTML_BYTES=5242880

# CORS settings (allows extension to connect)
CORS_ALLOWED_ORIGINS=["chrome-extension://*"]
```

**💡 Tip:** Keep the default values unless you have specific requirements.

### Step 6: Run the Development Server

Start the backend server:

```bash
# Using Poetry
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Or if using pip
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

You should see output like:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345] using StatReload
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**What the flags mean:**
- `--reload` - Auto-restart when code changes (development only)
- `--host 0.0.0.0` - Accept connections from any network interface
- `--port 8000` - Run on port 8000

### Step 7: Verify the Backend is Working

Open a new terminal and test the health check endpoint:

```bash
# Using curl
curl http://localhost:8000/health

# Or using your browser
# Navigate to: http://localhost:8000/health
```

You should see a response like:
```json
{
  "status": "healthy",
  "version": "1.0.0"
}
```

**✅ Success!** Your backend is now running and ready to process requests.

**💡 Tip:** Keep this terminal window open. The backend needs to stay running while you use the extension.

---

## 🧩 Extension Setup

### Step 1: Navigate to Extension Directory

Open a new terminal (keep the backend running in the other one):

```bash
cd /home/nik/bob-project/ibm-extension-v4
```

### Step 2: Open Chrome Extensions Page

1. Open Google Chrome
2. Navigate to `chrome://extensions/`
3. Or use the menu: **⋮ (Menu) → Extensions → Manage Extensions**

### Step 3: Enable Developer Mode

In the top-right corner of the Extensions page, toggle **Developer mode** to ON.

![Developer Mode Toggle](https://via.placeholder.com/400x100?text=Toggle+Developer+Mode+ON)

You should now see additional buttons: "Load unpacked", "Pack extension", and "Update".

### Step 4: Load the Extension

1. Click the **"Load unpacked"** button
2. Navigate to your project directory
3. Select the `ibm-extension-v4` folder
4. Click **"Select Folder"** (or "Open" on some systems)

The extension should now appear in your extensions list with:
- Name: **DOM Patch Assistant**
- Status: **Enabled**
- ID: A unique extension ID

### Step 5: Configure Extension Options

1. Click the **"Details"** button on the extension card
2. Scroll down and click **"Extension options"**
3. Verify the API URL is set to: `http://localhost:8000`
4. Ensure the extension is **Enabled**
5. Click **"Save"** if you made any changes

**Default Configuration:**
```
API Base URL: http://localhost:8000
Extension Status: Enabled
```

### Step 6: Pin Extension to Toolbar

For easy access:

1. Click the **puzzle piece icon** (🧩) in Chrome's toolbar
2. Find **DOM Patch Assistant** in the list
3. Click the **pin icon** (📌) next to it

The extension icon should now appear in your toolbar for quick access.

### Step 7: Enable File URL Access (Optional)

If you want to test on local HTML files:

1. On the extension's details page
2. Scroll to **"Allow access to file URLs"**
3. Toggle it **ON**

---

## 🎯 First Use

Let's make your first webpage modification!

### Step 1: Open a Test Webpage

You have two options:

**Option A: Use the Included Test Page**
```bash
# Open the test page in Chrome
# Navigate to: file:///home/nik/bob-project/ibm-extension-v4/test-pages/selector-stability.html
```

**Option B: Use Any Live Website**

Try a simple website like:
- `https://example.com`
- `https://wikipedia.org`
- Any news website or blog

**💡 Tip:** Start with simpler pages for your first attempts. Complex web applications may have dynamic content that's harder to modify.

### Step 2: Open the Extension Popup

Click the **DOM Patch Assistant** icon in your Chrome toolbar.

You should see:
- A text input field for your command
- An "Apply Changes" button
- A status indicator showing "Backend: Connected ✓"

### Step 3: Try Example Commands

Enter one of these commands in the text field:

**Simple Styling:**
```
Make all headings blue
```

**Layout Changes:**
```
Hide the sidebar
```

**Content Modification:**
```
Add a red border to all images
```

**Advanced:**
```
Move the navigation menu to the top right corner
```

### Step 4: Apply the Changes

1. Type your command in the input field
2. Click **"Apply Changes"**
3. Wait a few seconds (you'll see a loading indicator)
4. Watch the page transform!

**What's Happening Behind the Scenes:**
1. Extension captures the page HTML
2. Sends HTML + your command to the backend
3. Backend preprocesses the HTML
4. OpenAI generates DOM manipulation patches
5. Backend validates and returns patches
6. Extension applies patches to the page

### Step 5: Understand the Response

After applying changes, you'll see:
- **Success message** - "Changes applied successfully!"
- **Patch count** - Number of DOM operations performed
- **Timing info** - How long the operation took

Example response:
```
✓ Applied 3 patches in 2.4s
- Modified 2 elements
- Added 1 style rule
```

### Step 6: View Cached Changes

The extension automatically caches successful changes:

1. Reload the page (F5 or Ctrl+R)
2. The same modifications will be reapplied automatically
3. No need to re-enter the command!

**Cache Key:** Changes are cached per `origin + pathname`, so:
- `https://example.com/page1` and `https://example.com/page2` have separate caches
- Query parameters (`?id=123`) are ignored
- Hash fragments (`#section`) are ignored

---

## 🧪 Testing the Setup

Let's verify everything is working correctly.

### Test 1: Use the Included Test Page

1. Open: `file:///home/nik/bob-project/ibm-extension-v4/test-pages/selector-stability.html`
2. Open the extension popup
3. Try: `"Make the header background blue"`
4. Verify the header changes color

**Expected Result:** The header should turn blue immediately.

### Test 2: Try Different Commands

Test various command types:

**Styling:**
```
Change all paragraph text to green
```

**Visibility:**
```
Hide all images
```

**Layout:**
```
Center all text on the page
```

**Attributes:**
```
Add a tooltip to all links saying "Click me"
```

### Test 3: Check Backend Logs

In the terminal where your backend is running, you should see logs like:

```
INFO:     127.0.0.1:54321 - "POST /api/v1/process HTTP/1.1" 200 OK
INFO:     Processing request for use_case=dom_manipulation
INFO:     Preprocessed HTML: 1234 tokens
INFO:     AI call completed in 1.8s
INFO:     Returning 3 patches
```

**💡 Tip:** These logs are helpful for debugging and understanding what's happening.

### Test 4: Verify Caching Works

1. Apply a change to a page
2. Reload the page (F5)
3. The changes should reappear automatically
4. Check the extension popup - it should show "Cached patches reapplied"

### Test 5: Clear Cache

To remove cached changes:

1. Open the extension popup
2. Click **"Clear Cache"** button
3. Reload the page
4. The page should return to its original state

---

## 🔧 Common Setup Issues

### Issue 1: Port Already in Use

**Error:**
```
ERROR: [Errno 48] Address already in use
```

**Solution:**

Find and kill the process using port 8000:

```bash
# Find the process
lsof -i :8000

# Kill it (replace PID with the actual process ID)
kill -9 PID

# Or use a different port
uvicorn app.main:app --reload --port 8001
```

If using a different port, update the extension options to match.

### Issue 2: OpenAI API Key Errors

**Error:**
```
401 Unauthorized: Invalid API key
```

**Solutions:**

1. **Verify your API key:**
   - Check it's correctly copied in `.env`
   - No extra spaces or quotes
   - Starts with `sk-`

2. **Check API key validity:**
   - Log in to [OpenAI Platform](https://platform.openai.com/api-keys)
   - Verify the key exists and is active
   - Check you have available credits

3. **Restart the backend:**
   ```bash
   # Stop the server (Ctrl+C)
   # Start it again
   poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Issue 3: Extension Not Loading

**Error:**
```
Manifest file is missing or unreadable
```

**Solutions:**

1. **Verify the correct folder:**
   - Make sure you selected `ibm-extension-v4/` not the parent directory
   - The folder should contain `manifest.json`

2. **Check manifest.json:**
   ```bash
   # Verify the file exists
   ls ibm-extension-v4/manifest.json
   ```

3. **Reload the extension:**
   - Go to `chrome://extensions/`
   - Click the refresh icon on the extension card
   - Or remove and re-add the extension

### Issue 4: CORS Issues

**Error in browser console:**
```
Access to fetch at 'http://localhost:8000' from origin 'chrome-extension://...' has been blocked by CORS policy
```

**Solutions:**

1. **Check backend CORS settings:**
   ```env
   # In .env file
   CORS_ALLOWED_ORIGINS=["chrome-extension://*"]
   ```

2. **Restart the backend** after changing `.env`

3. **Verify the backend is running:**
   ```bash
   curl http://localhost:8000/health
   ```

### Issue 5: Backend Not Responding

**Symptoms:**
- Extension shows "Backend: Disconnected ✗"
- Health check fails

**Solutions:**

1. **Check if backend is running:**
   ```bash
   # Should show the uvicorn process
   ps aux | grep uvicorn
   ```

2. **Check the correct port:**
   ```bash
   # Test the health endpoint
   curl http://localhost:8000/health
   ```

3. **Check firewall settings:**
   - Ensure port 8000 is not blocked
   - Try accessing from browser: `http://localhost:8000/health`

4. **Review backend logs:**
   - Look for error messages in the terminal
   - Check for Python exceptions

### Quick Troubleshooting Checklist

- [ ] Backend is running (`curl http://localhost:8000/health` works)
- [ ] OpenAI API key is set in `.env`
- [ ] Extension is loaded in Chrome (`chrome://extensions/`)
- [ ] Extension has correct API URL in options
- [ ] No CORS errors in browser console (F12)
- [ ] Port 8000 is not blocked by firewall

---

## 🎓 Next Steps

Congratulations! You now have a working DOM Patch Assistant setup. Here's what to explore next:

### Learn More

- **[Architecture Guide](../ARCHITECTURE.md)** - Understand how the system works under the hood
- **[Working with Bob](WORKING_WITH_BOB.md)** - Learn about the AI-assisted development process
- **[Full HTML Pipeline](../FULL_HTML_PIPELINE.md)** - Deep dive into HTML processing

### Experiment

Try more complex commands:
- Combine multiple changes: `"Make headings blue and add borders to images"`
- Layout transformations: `"Convert the page to a two-column layout"`
- Theme changes: `"Apply a dark theme to the entire page"`

### Explore the Code

- **Backend:** `backend/app/` - FastAPI application and AI integration
- **Extension:** `ibm-extension-v4/` - Chrome extension code
- **Prompts:** `backend/app/prompts/` - AI prompt templates

### Advanced Usage

- **Custom Preprocessing:** Modify `backend/app/preprocessing/` for different HTML handling
- **New Handlers:** Add new use cases in `backend/app/handlers/`
- **Prompt Engineering:** Tune prompts in `backend/app/prompts/dom_manipulation/`

### Development

If you want to contribute or modify the project:

```bash
# Run backend tests
cd backend
poetry run pytest

# Format code
poetry run black .
poetry run ruff check --fix .

# Type checking
poetry run mypy app
```

### Get Help

- **Issues:** Report bugs or request features on GitHub
- **Discussions:** Ask questions and share ideas
- **Documentation:** Check the docs folder for more guides

---

## 💡 Tips for Best Results

1. **Start Simple:** Begin with basic styling commands before trying complex layouts
2. **Be Specific:** Clear, specific commands work better than vague ones
3. **Iterate:** If a command doesn't work perfectly, try rephrasing it
4. **Check Logs:** Backend logs provide insight into what's happening
5. **Use Test Pages:** The included test page is great for experimentation
6. **Cache Management:** Clear cache when testing different approaches
7. **Inspect Elements:** Use Chrome DevTools to understand page structure

---

## 🎉 You're Ready!

You've successfully set up the DOM Patch Assistant and made your first webpage modifications. The system is now ready for you to explore and experiment with.

**Remember:**
- Keep the backend running while using the extension
- Your OpenAI API usage will be billed according to your plan
- Changes are cached per page for automatic reapplication
- You can always clear the cache to start fresh

Happy modifying! 🚀

---

**Need Help?** Check the [troubleshooting section](#-common-setup-issues) or review the [architecture documentation](../ARCHITECTURE.md) for more details.