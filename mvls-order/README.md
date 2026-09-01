# MVLS Order Form AI Skill

An AI assistant skill that automates filling out the official **University of Glasgow MVLS Supplier Requisition Form (Excel)**.

Stop copying and pasting catalogue numbers, product descriptions, and prices by hand. Just give your AI assistant a link, quote text, or screenshot, and it will generate a fully completed, formatted, and ready-to-sign `.xlsx` requisition form!

### ✨ What it does for you:
- **Instant Product Extraction**: Pulls product names, catalogue codes, pack sizes, and ex-VAT prices from supplier URLs, pasted text, or screenshots.
- **Batch Splitting**: Automatically splits orders across multiple suppliers or into multiple sheets if you exceed the 11-item limit per requisition form.
- **Flawless Excel Formatting**: Retains all official University dropdowns (School, Tax Codes, Radiation flags), formulas, and layouts without corrupting the file.
- **One-Click Delivery**: Saves the completed requisition form directly in your project folder ready for signature and submission.

---

## 🚀 Beginner-Friendly Setup (No Coding Required!)

You don't need any programming knowledge or terminal experience to use this skill. Your AI assistant can handle the installation and setup for you.

---

### Step 1: Download the Skill from GitHub

1. Go to the repository page on GitHub.
2. Click the green **`<> Code`** button near the top right.
3. Select **Download ZIP**.
4. Unzip (extract) the downloaded file on your computer (e.g. in your `Downloads` or `Documents` folder). You will see a folder named `mvls-order`.

---

### Step 2: Install the Skill Using AI Chat

You can install this skill either **Globally** (available in all your chats and projects) or in a specific **Workspace** (available only within the current project folder).

Open your AI assistant chat (such as Antigravity, Cursor, or VS Code AI Chat) and simply paste one of the prompts below:

#### Option A: Install Globally (Recommended)
Paste this in your AI chat:
> *"I downloaded the `mvls-order` skill folder. Please help me install it as a global skill so I can use it across any project (copy it to `~/.gemini/config/skills/mvls-order` or `~/.gemini/antigravity/skills/mvls-order`)."*

#### Option B: Install in Your Current Workspace
Paste this in your AI chat:
> *"Please help me install the `mvls-order` folder into this workspace under `.agents/skills/mvls-order`."*

The AI assistant will automatically create the required directories, copy the files into place, and confirm when the skill is installed.

> [!TIP]
> **Manual Alternative (Drag & Drop)**:
> If you prefer moving files manually without AI chat:
> - **Global**: Move `mvls-order` to `~/.gemini/config/skills/mvls-order` (Mac/Linux) or `%USERPROFILE%\.gemini\config\skills\mvls-order` (Windows).
> - **Workspace**: Create a folder named `.agents/skills/` in your workspace and drop `mvls-order` inside it.

---

### Step 3: Configure Your Lab Details via AI Chat

Before your first order, the skill needs your contact details and lab grant codes to pre-fill the form correctly.

In your AI chat, simply say:
> *"Set up mvls-order"* or *"Configure mvls-order defaults"*

Your AI assistant will guide you through a quick setup by asking for:
1. **Your Full Name** (Orderer name)
2. **Your Glasgow Email Address**
3. **Your Room & Building**
4. **Your Frequently Used Grants & Project Codes** (e.g. *Grant nickname:* `Wellcome`, *Project code:* `123456-01`)

The AI will automatically update the configuration for you. You only need to do this once!

---

### Step 4: Place Your First Order!

Once installed and configured, filling out an order requisition is as simple as chatting with your AI.

Just paste a product link into the chat:
> *"mvls-order https://www.agarscientific.com/five-slide-mailer on grant Wellcome, quantity 2"*

Or paste text from a quote or email:
> *"mvls-order: Please order 5 packs of cat# 123-456 from Sigma on my MRC grant."*

Or attach a screenshot of the product page/cart!

The AI assistant will:
1. Confirm the grant and quantity.
2. Fetch the product details and price.
3. Generate the completed `.xlsx` requisition form in your workspace.
4. Provide a clickable link so you can open, review, and sign it!

---

## ⚙️ Alternative Setup: Interactive Terminal Wizard (For Coders)

If you prefer using the command line, you can run the interactive setup script directly:

```bash
cd mvls-order
python3 scripts/setup.py
```
This wizard will prompt you in the terminal for your details and update your configuration automatically.

---

## 🧩 Compatibility Across AI Assistants

This skill is built with pure Python standard library modules (`zipfile`, `json`, `re`, `pathlib`) and has zero third-party dependencies.

| Assistant / Tool | How to Use |
| :--- | :--- |
| **Antigravity** | Auto-discovers skills from `~/.gemini/config/skills/` or `.agents/skills/`. Simply type `"mvls-order <url>"`. |
| **Cursor / VS Code Chat** | Slash command `/mvls-order` in chat or add the skill to your custom rules. |
| **Claude Desktop** | Package with `zip -r mvls-order.skill mvls-order/` and drop into Claude's skills library. |

---

## 📁 Skill Structure

- **`SKILL.md`**: Core instructions, form rules, dropdown options, and your saved lab defaults/grants.
- **`scripts/fill_order.py`**: Pure-Python engine that populates the Excel form XML directly, preserving all official University formulas and dropdown validations.
- **`scripts/setup.py`**: Interactive CLI setup wizard script.
- **`assets/mvls_requisition_template.xlsx`**: Official MVLS supplier requisition template.

