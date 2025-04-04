import frappe
import os
import requests
import asyncio
from deepgram import Deepgram

# from dotenv import load_dotenv
import google.generativeai as genai
import json
import re
import time

# # Load environment variables
# load_dotenv()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")

# def monthly_pocket_money_scheduler():
#     family_members = frappe.get_all("Family Member", fields=["full_name", "telegram_id", "pocket_money", "rollover_savings", "primary_account_holder"])

#     for member in family_members:
#         pocket_money = member.pocket_money or 0
#         rollover_savings = member.rollover_savings or 0

#         new_roll_over = rollover_savings + pocket_money

#         frappe.db.set_value("Family Member", member.name, {
#             "rollover_savings": new_roll_over,
#             "pocket_money": 0
#         })

#         current_month = datetime.datetime.now().strftime("%B")

#         message = f"""
#             💰 Monthly Savings Summary\\!

#             Hey {member.full_name}, here’s your savings update for {current_month}:

#             Keep up the good savings habits\!
#         """

#         send_telegram_message(member.telegram_id, message)

# primary_accounts = frappe.get_all("Primary Account", fields=["name", "total_expense", "default_pocket_money_for_dependents"])

# for account in primary_accounts:
#     frappe.db.set_value("Primary Account", account.name, "total_expense", 0)

# for account in primary_accounts:
#     family_members = frappe.get_all("Family Member", filters={"primary_account_holder": account.name}, fields=["name"])

#     for member in family_members:
#         frappe.db.set_value("Family Member", member.name, "pocket_money", account.default_pocket_money_for_dependents)

#     total_expenses = account.default_pocket_money_for_dependents * len(family_members)
#     frappe.db.set_value("Primary Account", account.name, "total_expense", total_expenses)

# frappe.db.commit()


# def monthly_savings_summary():
#     family_members = frappe.get_all(
#         "Family Member",
#         fields=["full_name", "telegram_id", "pocket_money", "primary_account_holder"],
#     )

#     current_month = datetime.datetime.now().strftime("%B")

#     for member in family_members:
#         chat_id = member.telegram_id.strip()

#         total_expenses = frappe.db.get_value(
#             "Expense Entry",
#             {"associated_account_holder": member.primary_account_holder},
#             "SUM(amount)"
#         ) or 0.0

#         savings = max(0, member.pocket_money - total_expenses)

#         message = f"""
#             💰 Monthly Savings Summary\!

#             Hey {member.full_name}, here’s your savings update for {current_month}:

#             🏦 Pocket Money Given\: {member.pocket_money:.2f} INR
#             💸 Total Expenses\: {total_expenses:.2f} INR
#             💰 Savings This Month\: {savings:.2f} INR

#             Keep up the good savings habits\!
#         """

#         message = message.replace(":.2f", ":\\.2f")  # Escape dots for Telegram MarkdownV2

#         print(message)  # Debugging
#         send_telegram_message(chat_id, message)


def get_audio_file_path():
    """Fetch the latest uploaded audio file path from File Doctype."""
    file_doc = frappe.get_list(
        "File", filters={"file_url": "/files/food.mp4"}, fields=["file_url"], limit=1
    )

    if file_doc:
        file_url = file_doc[0]["file_url"]  # "/files/food.mp4"
        site_path = frappe.get_site_path(
            "public", file_url.lstrip("/")
        )  # Convert to absolute path
        return site_path
    return None


async def transcribe_audio_async(file_url, chat_id):
    """Asynchronous function to transcribe audio using Deepgram API."""
    try:
        # audio_path = frappe.get_site_path("public", file_url.lstrip("/"))
        # if not audio_path:
        #     print("No audio file found.")
        #     return None

        deepgram = Deepgram(DEEPGRAM_API_KEY)

        # with open(audio_path, "rb") as audio:
        #     buffer_data = audio.read()

        # options = {
        #     "punctuate": True,
        #     "model": "nova",
        #     "language": "en",
        # }

        # response = await deepgram.transcription.prerecorded(
        #     {"buffer": buffer_data, "mimetype": "audio/ogg"},
        #     options
        # )

        response = await deepgram.transcription.prerecorded(
            {"url": file_url},  # Use direct URL instead of reading the file
            {"punctuate": True, "model": "nova", "language": "en"},
        )

        transcript = response["results"]["channels"][0]["alternatives"][0]["transcript"]
        # print("Transcription:", transcript)

        escaped_transcript = transcript.replace(".", "\\.").replace("!", "\\!")

        message = """
        ⏳ *Processing...* 🎙️  
  
Hold tight! We're transcribing your audio...   
        """

        message = message.replace(".", "\\.").replace("!", "\\!")

        send_telegram_message(chat_id, message)
        await asyncio.sleep(2)
        message1 = """
Almost Done\!
"""
        send_telegram_message(chat_id, message1)
        time.sleep(4)
        extract_and_notify(transcript, escaped_transcript, chat_id)
        return transcript

    except Exception as e:
        print(f"Error in transcription: {e}")
        return None


def extract_details_from_text(text):
    """Uses Gemini AI to extract structured details from text."""
    try:
        genai.configure(api_key=GEMINI_API_KEY)

        prompt = f"""
        Extract structured details from the following text:
        "{text}"

        Output the details in **strict** JSON format with these keys:
        - amount (numeric, float)
        - category (string, like Food, Transport, etc.)
        - merchant (string, store or service name)

        Example output (no additional text, just JSON):
        {{
            "amount": 120.50,
            "category": "Food",
            "merchant": "Dominos"
        }}
        """

        model = genai.GenerativeModel("gemini-1.5-pro-latest")
        response = model.generate_content(prompt)

        # Ensure response is in JSON format
        extracted_data = response.text.strip()

        # Debugging: Print the raw response
        print("Raw Gemini Response:", extracted_data)

        # Remove backticks and unnecessary formatting
        cleaned_json = re.sub(r"```json|```", "", extracted_data).strip()

        # Try parsing JSON safely
        try:
            details = json.loads(cleaned_json)
        except json.JSONDecodeError:
            print("Error: Gemini response is not valid JSON")
            return None

        print("Extracted Details:", details)
        return details

    except Exception as e:
        print(f"Error in extracting details: {e}")
        return None


def transcribe_audio(file_url, chat_id):
    """Wrapper to run async function in sync mode using asyncio.run()"""
    return asyncio.run(transcribe_audio_async(file_url, chat_id))


@frappe.whitelist(allow_guest=True)
def process_and_notify(file_url, chat_id):
    """Transcribe audio and send it as a Telegram message."""
    return transcribe_audio(file_url, chat_id)


def escape_markdown_v2(text):
    """Escapes special characters for Telegram MarkdownV2."""
    if text is None:
        return "Unknown"  # Ensure None values are converted to safe text

    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(
        r"([" + re.escape(escape_chars) + r"])", r"\\\1", str(text)
    )  # Ensure conversion to string

def extract_and_notify(text, escaped_transcript, chat_id):
    """Extract details from text and send as a Telegram notification."""
    try:
        extracted_details = extract_details_from_text(text)
        if extracted_details:
            amount = escape_markdown_v2(f"{extracted_details.get('amount', 'N/A'):.2f}")
            category = escape_markdown_v2(extracted_details.get("category", "N/A"))
            merchant = escape_markdown_v2(extracted_details.get("merchant", "N/A"))

            is_primary = frappe.db.exists("Primary Account", {"telegram_id": chat_id})
            is_family = frappe.db.exists("Family Member", {"telegram_id": chat_id})

            frappe.logger().info(f"Extracted Details: {extracted_details}, Chat ID: {chat_id}, Is Primary: {is_primary}, Is Family: {is_family}")

            if is_family:
                try:
                    family_member_doc = frappe.get_doc("Family Member", {"telegram_id": chat_id})
                    primary_account_holder_id = family_member_doc.primary_account_holder

                    allowed_categories = [
                        d.category_type
                        for d in frappe.get_all(
                            "Expense Category",
                            filters={"associated_account_holder": primary_account_holder_id},
                            fields=["category_type"],
                        )
                    ]

                    if category not in allowed_categories:
                        primary_account_doc = frappe.get_doc("Primary Account", {"name": primary_account_holder_id})
                        family_message = f"⚠️ *Restricted Category!* Your transaction under '{category}' is not permitted."
                        parent_message = f"📢 *Expense Alert!* {family_member_doc.full_name} attempted a transaction in the '{category}' category, which is not part of the permitted expenses."

                        family_escaped_message = family_message.replace(".", "\\.").replace("!", "\\!").replace("*", "\\*").replace("_", "\\_")
                        parent_escaped_message = parent_message.replace(".", "\\.").replace("!", "\\!").replace("*", "\\*").replace("_", "\\_")

                        send_telegram_message(chat_id, family_escaped_message)
                        send_telegram_message(primary_account_doc.telegram_id, parent_escaped_message)
                        return
                    else:
                        expense_category_type_doc = frappe.get_doc(
                            "Expense Category",
                            filters={
                                "associated_account_holder": primary_account_holder_id,
                                "category_type": category,
                            },
                        )
                        expense_category_type_doc.budget -= extracted_details.get("amount", 0.0)
                        expense_category_type_doc.save(ignore_permissions=True)
                        frappe.db.commit()
                except Exception as e:
                    frappe.log_error(f"Error processing family member transaction: {str(e)}")

            else:
                try:
                    primary_account_doc = frappe.get_doc("Primary Account", {"telegram_id": chat_id})
                    allowed_categories = [
                        d.category_type
                        for d in frappe.get_all(
                            "Expense Category",
                            filters={"associated_account_holder": primary_account_doc.name},
                            fields=["category_type"],
                        )
                    ]

                    if category not in allowed_categories:
                        warning_message = f"⚠️ *Unrecognized Category!* The category '{category}' is not listed under your approved expense categories."
                        escaped_message = warning_message.replace(".", "\\.").replace("!", "\\!").replace("*", "\\*").replace("_", "\\_")
                        send_telegram_message(chat_id, escaped_message)
                        return
                    else:
                        expense_category_type_doc = frappe.get_doc(
                            "Expense Category",
                            filters={
                                "associated_account_holder": primary_account_doc.name,
                                "category_type": category,
                            },
                        )
                        expense_category_type_doc.budget -= float(extracted_details.get("amount", 0.0))
                        expense_category_type_doc.save(ignore_permissions=True)
                        frappe.db.commit()
                except Exception as e:
                    frappe.log_error(f"Error processing primary account transaction: {str(e)}")

            if is_primary:
                try:
                    primary_account = frappe.get_doc("Primary Account", {"telegram_id": chat_id})
                    primary_account.salary -= extracted_details.get("amount", 0.0)
                    primary_account.save(ignore_permissions=True)
                    frappe.db.commit()
                except Exception as e:
                    frappe.log_error(f"Error updating primary account balance: {str(e)}")
            elif is_family:
                try:
                    family_member = frappe.get_doc("Family Member", {"telegram_id": chat_id})
                    if family_member.pocket_money >= extracted_details.get("amount", 0.0):
                        family_member.pocket_money -= extracted_details.get("amount", 0.0)
                        family_member.save(ignore_permissions=True)
                        frappe.db.commit()
                    else:
                        send_telegram_message(chat_id, "⚠️ *Insufficient pocket money!* Please request more funds.")
                        return
                except Exception as e:
                    frappe.log_error(f"Error updating family member pocket money: {str(e)}")

            keyboard = [
                [{"text": "💰 Check Balance", "callback_data": "check_balance"}],
                [{"text": "📊 View Report - CS", "callback_data": "view_report"}],
            ]

            if is_primary:
                keyboard.append([{ "text": "➕ Add Money", "callback_data": "add_money"}])
            elif is_family:
                keyboard.append([{ "text": "🛎️ Request Money", "callback_data": "request_money"}])

            message = f"""
🎙️ *Transcription Complete\!*\n\n*{escaped_transcript}*\n\n
💡 *Expense Details Extracted* 💡\n\n
💰 *Amount:* {amount}  \n
📂 *Category:* {category}  \n
🏪 *Merchant:* {merchant}  \n\n
✅ *This record has been automatically saved in the Expense Doctype\!*\n\n
📊 _Effortless tracking for smarter spending\!_ \n            

"""

            try:
                expense = frappe.get_doc(
                    {
                        "doctype": "Expense",
                        "user_id": chat_id,
                        "amount": extracted_details.get("amount", 0.0),
                        "category": category,
                        "merchant": merchant,
                        "date": frappe.utils.now_datetime(),
                        "description": text,
                        "payment_mode": "UPI",
                        "source": "Telegram Bot",
                    }
                )
                expense.insert(ignore_permissions=True)
                send_telegram_message_with_keyboard(chat_id, message, keyboard)
            except Exception as e:
                frappe.log_error(f"Error inserting expense record: {str(e)}")
        else:
            send_telegram_message(chat_id, "❌ Sorry, we couldn't extract the details from the text provided\.")
    except Exception as e:
        frappe.log_error(f"Unexpected error in extract_and_notify: {str(e)}")

# def weekly_spending_summary():

#     family_members = frappe.get_all(
#         "Family Member",
#         fields=["full_name", "telegram_id", "pocket_money", "primary_account_holder"],
#     )

#     current_week = datetime.datetime.now().isocalendar()[1]
#     total_weeks = 4

#     remaining_weeks = total_weeks - ((current_week - 1) % total_weeks)

#     for member in family_members:

#         chat_id = member.telegram_id.strip()

#         categories = frappe.get_all(
#             "Expense Category",
#             filters={"associated_account_holder": member.primary_account_holder},
#             fields=["category_type"],
#         )

#         category_names = [cat["category_type"] for cat in categories]

#         weekly_budget = member.pocket_money / remaining_weeks

#         def escape_dots(text):
#             return str(text).replace(".", "\\.")

#         suggestions = [f"Consider spending around *{weekly_budget:.2f}* per week."]
#         if "Food" in category_names:
#             suggestions.append("🍽️ Prioritize meals over snacks to save more!")
#         if "Entertainment" in category_names:
#             suggestions.append(
#                 "🎬 Keep entertainment spending within limits for a balanced budget."
#             )
#         if "Transport" in category_names:
#             suggestions.append("🚖 Use public transport or pooling to save costs.")

#         name = member.full_name
#         pockey_money_left = member.pocket_money

#         message = f"""
#             *📊 Weekly Spending Summary\\!*

#             Hey {name}, here’s your spending insight for the remaining {remaining_weeks} weeks:

#             🏦 *Pocket Money Left\\:* {pockey_money_left:.2f} INR
#             📌 *Remaining Weeks\\:* {remaining_weeks}
#             🔖 *Allowed Categories\\:* {', '.join(category_names)}

#             🔹 {suggestions[0]}
#             🔹 {suggestions[1] if len(suggestions) > 1 else ''}

#             _Plan wisely and make the most out of your budget\\!_
#         """

#         message = message.replace(":.2f", ":\\.2f") #escape the dot here.

#         print(message)

#         send_telegram_message(chat_id, message)


def send_telegram_message(chat_id, message):

    bot_token = os.getenv("BOT_TOKEN")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "MarkdownV2"}

    try:
        response = requests.post(url, json=payload)
        response_data = response.json()
        print(response_data)

        if not response_data.get("ok"):
            frappe.logger().error(
                f"Failed to send Telegram notification: {response_data}"
            )
    except Exception as e:
        frappe.logger().error(f"Error sending Telegram message: {str(e)}")


def send_telegram_message_with_keyboard(chat_id, message, keyboard):
    bot_token = os.getenv("BOT_TOKEN")

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "MarkdownV2",
        "reply_markup": {"inline_keyboard": keyboard},
    }

    try:
        response = requests.post(url, json=payload)
        response_data = response.json()
        print(response_data)

        if not response_data.get("ok"):
            frappe.logger().error(
                f"Failed to send Telegram notification: {response_data}"
            )
    except Exception as e:
        frappe.logger().error(f"Error sending Telegram message: {str(e)}")


# @frappe.whitelist(allow_guest=True)
# def telegram_webhook():
#     try:
#         data = frappe.request.get_data(as_text=True)
#         data = json.loads(data)

#         if "message" in data:
#             chat_id = data["message"]["chat"]["id"]
#             text = data["message"].get("text", "")

#             if text == "/start":
#                 send_telegram_message(chat_id, "Hello you are now registered for updates")

#         return {"ok": True}

#     except Exception as e:
#         frappe.log_error(f"Telegram Webhook Error: {str(e)}")
#         return {"ok": False, "error": str(e)}


@frappe.whitelist(allow_guest=True)
def telegram_webhook():
    try:
        data = frappe.request.get_data(as_text=True)
        data = json.loads(data)

        if "callback_query" in data:
            callback_query = data["callback_query"]
            chat_id = callback_query["message"]["chat"]["id"]
            callback_data = callback_query["data"]

            # frappe.cache.set_value(f"callback_{chat_id}", callback_data)

            if callback_data == "role_parent":
                frappe.cache.set_value(f"callback_{chat_id}", callback_data)
                message = "Please enter your *Parent ID* to continue."
            elif callback_data == "role_dependent":
                frappe.cache.set_value(f"callback_{chat_id}", callback_data)
                message = "Please enter your *Parent ID* for verification."
            elif callback_data == "check_balance":
                message = get_balance(chat_id)
            elif callback_data == "add_money":
                frappe.cache.set_value(f"callback_{chat_id}", callback_data)
                message = "➕ *Enter the amount you want to add.*"
            elif callback_data == "request_money":
                frappe.cache.set_value(f"callback_{chat_id}", callback_data)
                message = "💸 *Enter the amount you want to request.*"
            elif callback_data == "view_report":
                message = "📊 *Report Unavailable!* This feature is currently under development. Stay tuned for updates."
            if callback_data == "set_monthly_budget":
                frappe.cache.set_value(f"set_budget_{chat_id}", True)
                message = """
            🎙️ *Send a voice note describing your budget for each category!*  
            For example:  
            "_Food ₹5000, Travel ₹3000, Shopping ₹2000_"  
            """
            elif callback_data == "approve":
                approve_money_request(chat_id)
                return {"ok": True}
            elif callback_data == "deny":
                deny_money_request(chat_id)
                return {"ok": True}

            escaped_message = (
                message.replace(".", "\\.")
                .replace("!", "\\!")
                .replace("*", "\\*")
                .replace("_", "\\_")
            )
            send_telegram_message(chat_id, escaped_message)
            return {"ok": True}

        if "message" in data:
            chat_id = data["message"]["chat"]["id"]
            first_name = data["message"]["from"].get("first_name", "User")
            last_name = data["message"]["from"].get("last_name", "")
            text = data["message"].get("text", "")

            if text == "/start":
                welcome_message = (
                    "👋 Welcome to *ExpenseTrackerBot*! 📊💰\n\n"
                    "To get started, please select your role:\n\n"
                    "👨‍👩‍👧‍👦 *Are you a Parent or a Dependent?*"
                )

                keyboard = [
                    [{"text": "👨‍👩‍👦 Primary", "callback_data": "role_parent"}],
                    [{"text": "🧑‍🎓 Dependent", "callback_data": "role_dependent"}],
                ]

                escaped_message = (
                    welcome_message.replace(".", "\\.")
                    .replace("!", "\\!")
                    .replace("*", "\\*")
                    .replace("_", "\\_")
                )
                send_telegram_message_with_keyboard(chat_id, escaped_message, keyboard)

            elif "voice" in data["message"]:
                if frappe.cache.get_value(f"set_budget_{chat_id}"):
                    voice_file_id = data["message"]["voice"]["file_id"]
                    file_url = get_telegram_file_url(voice_file_id)

                    transcript = transcribe_voice_note_sync_wrapper(file_url)
                    process_budget_transcription(chat_id, transcript)

                    return

                primary_exist = frappe.db.exists(
                    "Primary Account", {"telegram_id": chat_id}
                )
                family_exist = frappe.db.exists(
                    "Family Member", {"telegram_id": chat_id}
                )

                if not (primary_exist or family_exist):
                    send_telegram_message(
                        chat_id,
                        "⚠️ You are not registered\! Please verify your account before using voice messages\.",
                    )
                    return

                voice_file_id = data["message"]["voice"]["file_id"]
                file_url = get_telegram_file_url(voice_file_id)

                if file_url:
                    file_doc = frappe.get_doc(
                        {
                            "doctype": "File",
                            "file_name": f"voice_{chat_id}.ogg",
                            "file_url": file_url,
                            "is_private": 1,
                        }
                    )
                    file_doc.insert(ignore_permissions=True)

                    process_and_notify(file_url, chat_id)

            else:

                user_role = frappe.cache.get_value(f"callback_{chat_id}")

                if user_role is None:
                    prompt = f"""
                    You are an AI assistant managing a Telegram Expense Tracker bot. 
                    A user has sent the following message: "{text}"

                    1️⃣ *If the message contains personal information* (like phone numbers, emails, addresses, etc.), 
                    reply: "🚨 Please avoid sharing personal information. This bot is only for tracking expenses."
                    
                    2️⃣ *If the message contains abusive or inappropriate language*, 
                    reply: "⚠️ Please maintain respectful communication. Let's keep this space friendly."
                    
                    3️⃣ *If it's a general query*, reply in 2-3 lines, strictly explaining how the bot helps with tracking expenses.  
                    Do not provide lengthy explanations, just a short and clear response.
                    """

                    genai.configure(api_key=GEMINI_API_KEY)
                    model = genai.GenerativeModel("gemini-1.5-pro-latest")

                    response = model.generate_content(prompt)

                    ai_response = (
                        response.text
                        if hasattr(response, "text")
                        else "Sorry, I couldn't process your request."
                    )
                    escaped_ai_response = (
                        ai_response.replace(".", "\\.")
                        .replace("!", "\\!")
                        .replace("*", "\\*")
                        .replace("_", "\\_")
                    )

                    send_telegram_message(chat_id, escaped_ai_response)
                else:
                    if user_role == "role_parent" or user_role == "role_dependent":
                        parent_exists = frappe.db.exists("Primary Account", text)

                        if not parent_exists:
                            message = "❌ Invalid Parent ID. Please try again."
                            escaped_message = (
                                message.replace(".", "\\.")
                                .replace("!", "\\!")
                                .replace("*", "\\*")
                                .replace("_", "\\_")
                            )
                            send_telegram_message(chat_id, escaped_message)
                            return {"ok": False, "error": "Invalid Parent ID"}

                        if user_role == "role_parent":
                            message = "🎉 *You are verified as a Parent!* Now, track your expenses daily! 💳"
                            escaped_message = (
                                message.replace(".", "\\.")
                                .replace("!", "\\!")
                                .replace("*", "\\*")
                                .replace("_", "\\_")
                            )

                            primary_account_doc = frappe.get_doc("Primary Account", text)
                            primary_account_doc.telegram_id = chat_id  
                            primary_account_doc.save(ignore_permissions=True)
                            frappe.db.commit()

                            send_telegram_message(chat_id, escaped_message)
                            return {"ok": True}

                        elif user_role == "role_dependent":
                            if frappe.db.exists("Family Member", {"telegram_id": chat_id}):
                                message = "✅ *You're already registered!* Start tracking your expenses now. 📊"
                                escaped_message = (
                                    message.replace(".", "\\.")
                                    .replace("!", "\\!")
                                    .replace("*", "\\*")
                                    .replace("_", "\\_")
                                )
                                send_telegram_message(chat_id, escaped_message)

                            else:
                                if frappe.db.exists("Family Member", {"telegram_id": chat_id}):
                                    message = "✅ *You're already registered!* Start tracking your expenses now. 📊"
                                    escaped_message = (
                                        message.replace(".", "\\.")
                                        .replace("!", "\\!")
                                        .replace("*", "\\*")
                                        .replace("_", "\\_")
                                    )
                                    send_telegram_message(chat_id, escaped_message)
                                    return {"ok": True}

                                main_user = frappe.get_doc("Primary Account", text)

                                family_member_doc = frappe.get_doc(
                                    {
                                        "doctype": "Family Member",
                                        "primary_account_holder": text,
                                        "full_name": f"{first_name} {last_name}",
                                        "pocket_money": main_user.default_pocket_money_for_dependents,
                                        "telegram_id": chat_id,
                                    }
                                )
                                family_member_doc.insert(ignore_permissions=True)

                                main_user.salary -= (
                                    main_user.default_pocket_money_for_dependents
                                )
                                main_user.save(ignore_permissions=True)
                                frappe.db.commit()

                                message = "🎉 *You are verified as a Dependent!* Now, track your expenses daily! 🏦"
                                escaped_message = (
                                    message.replace(".", "\\.")
                                    .replace("!", "\\!")
                                    .replace("*", "\\*")
                                    .replace("_", "\\_")
                                )
                                send_telegram_message(chat_id, escaped_message)

                    elif user_role == "add_money":
                        message = ""  

                        if text.isdigit():
                            amount = int(text)
                            primary_account_doc = frappe.get_doc("Primary Account", {"telegram_id": chat_id})

                            if primary_account_doc:
                                primary_account_doc.salary += amount
                                primary_account_doc.save(ignore_permissions=True)
                                frappe.db.commit()

                                message = f"✅ *₹{amount} has been added to your account!* \n💰 *New Balance:* ₹{primary_account_doc.salary}"
                            else:
                                message = "❌ *Error:* You are not a registered primary account holder."

                        else:
                            message = "⚠️ *Invalid amount.* Please enter a valid number."

                        escaped_message = message.replace(".", "\\.").replace("!", "\\!").replace("*", "\\*").replace("_", "\\_")
                        send_telegram_message(chat_id, escaped_message)

                    elif user_role == "request_money":
                        if text.isdigit():
                            amount = int(text)

                            try:
                                family_member_doc = frappe.get_doc("Family Member", {"telegram_id": chat_id})
                            except frappe.DoesNotExistError:
                                warning_message = "❌ *Error:* You are not registered as a family member."
                                escaped_message = warning_message.replace(".", "\\.").replace("!", "\\!").replace("*", "\\*").replace("_", "\\_")
                                send_telegram_message(chat_id, escaped_message)
                                return {"ok": False, "error": "Family Member not found"}

                            try:
                                primary_account_doc = frappe.get_doc("Primary Account", family_member_doc.primary_account_holder)
                            except frappe.DoesNotExistError:
                                warning_message = "❌ *Error:* Your parent account does not exist."
                                escaped_message = warning_message.replace(".", "\\.").replace("!", "\\!").replace("*", "\\*").replace("_", "\\_")
                                send_telegram_message(chat_id, escaped_message)
                                return {"ok": False, "error": "Parent Account not found"}

                            if not primary_account_doc.telegram_id:
                                warning_message = "❌ *Error:* Parent Telegram ID is missing."
                                escaped_message = warning_message.replace(".", "\\.").replace("!", "\\!").replace("*", "\\*").replace("_", "\\_")
                                send_telegram_message(chat_id, escaped_message)
                                return {"ok": False, "error": "Parent Telegram ID missing"}

                            frappe.cache.set_value(f"request_amount_{primary_account_doc.telegram_id}", amount)
                            frappe.cache.set_value(f"request_parent_{primary_account_doc.telegram_id}", chat_id)

                            # Notify dependent
                            success_message = f"⏳ *Request Sent!* ₹{amount} has been requested from your parent.\nWe will notify you once they respond. ✅"
                            escaped_message = success_message.replace(".", "\\.").replace("!", "\\!").replace("*", "\\*").replace("_", "\\_")
                            send_telegram_message(chat_id, escaped_message)

                            # Notify parent with options
                            parent_message = f"📢 *Money Request Alert!*\nYour dependent *{family_member_doc.full_name}* has requested ₹{amount}.\nWould you like to approve it?"
                            parent_escaped_message = parent_message.replace(".", "\\.").replace("!", "\\!").replace("*", "\\*").replace("_", "\\_")

                            keyboard = [
                                [{"text": "✅ Approve", "callback_data": "approve"}],
                                [{"text": "❌ Deny", "callback_data": "deny"}],
                            ]

                            send_telegram_message_with_keyboard(primary_account_doc.telegram_id, parent_escaped_message, keyboard)

                        else:
                            warning_message = "⚠️ *Invalid amount.* Please enter a valid number."
                            escaped_message = warning_message.replace(".", "\\.").replace("!", "\\!").replace("*", "\\*").replace("_", "\\_")
                            send_telegram_message(chat_id, escaped_message)
                            return {"ok": False, "error": "Invalid Amount"}

                    frappe.cache().delete_value(f"callback_{chat_id}")
                    return {"ok": True}

        return {"ok": True}

    except Exception as e:
        frappe.log_error(f"Telegram Webhook Error: {str(e)}")
        return {"ok": False, "error": str(e)}


def get_balance(chat_id):
    primary_account_salary = frappe.db.get_value(
        "Primary Account", {"telegram_id": chat_id}, "salary"
    )
    family_member_pockey_money = frappe.db.get_value(
        "Family Member", {"telegram_id": chat_id}, "pocket_money"
    )

    if primary_account_salary:
        return f"💰 *Your Current Balance:* ₹{primary_account_salary}"
    elif family_member_pockey_money:
        return f"🛍️ *Your Current Pocket Money Balance:* ₹{family_member_pockey_money}"
    else:
        return "⚠️ *You are not registered in our system.*"


def approve_money_request(parent_chat_id):
    amount = frappe.cache.get_value(f"request_amount_{parent_chat_id}")
    dependent_chat_id = frappe.cache.get_value(f"request_parent_{parent_chat_id}")

    amount = int(amount)

    primary_account_doc = frappe.get_doc("Primary Account", {"telegram_id": parent_chat_id})
    family_member_doc = frappe.get_doc("Family Member", {"telegram_id": dependent_chat_id})

    if primary_account_doc.salary >= amount:
        primary_account_doc.salary -= amount
        family_member_doc.pocket_money += amount

        primary_account_doc.save(ignore_permissions=True)
        family_member_doc.save(ignore_permissions=True)
        frappe.db.commit()

        parent_message = f"✅ *Request Approved!*\n₹{amount} has been transferred to {family_member_doc.full_name}."
        dependent_message = f"🎉 *Request Approved!*\nYour parent sent you ₹{amount}. Check your pocket money! 💰"

        parent_escaped_message = parent_message.replace(".", "\\.").replace("!", "\\!").replace("*", "\\*").replace("_", "\\_")
        dependent_escaped_message = dependent_message.replace(".", "\\.").replace("!", "\\!").replace("*", "\\*").replace("_", "\\_")

        keyboard = [
            [{"text": "💰 Check Balance", "callback_data": "check_balance"}]
        ]

        send_telegram_message_with_keyboard(
            parent_chat_id, parent_escaped_message, keyboard
        )
        send_telegram_message_with_keyboard(
            dependent_chat_id, dependent_escaped_message, keyboard
        )
    else:
        send_telegram_message(
            parent_chat_id,
            "❌ *Insufficient balance\!* You don’t have enough funds to approve this request\.",
        )
        send_telegram_message(
            dependent_chat_id,
            "❌ *Request Denied\!* Your parent does not have enough funds\.",
        )

    frappe.cache.delete_value(f"request_amount_{parent_chat_id}")
    frappe.cache.delete_value(f"request_parent_{parent_chat_id}")
    return {"ok": True}


def deny_money_request(parent_chat_id):
    dependent_chat_id = frappe.cache.get_value(f"request_parent_{parent_chat_id}")

    parent_message = "❌ *Request Denied!* You rejected the money request."
    dependent_message = "❌ *Request Denied!* Your parent rejected your request for money."

    parent_escaped_message = parent_message.replace(".", "\\.").replace("!", "\\!").replace("*", "\\*").replace("_", "\\_")
    dependent_escaped_message = dependent_message.replace(".", "\\.").replace("!", "\\!").replace("*", "\\*").replace("_", "\\_")

    send_telegram_message(parent_chat_id, parent_escaped_message)
    send_telegram_message(dependent_chat_id, dependent_escaped_message)

    frappe.cache.delete_value(f"request_amount_{parent_chat_id}")
    frappe.cache.delete_value(f"request_parent_{parent_chat_id}")
    return {"ok": True}

async def transcribe_voice_note(file_url):
    deepgram = Deepgram(DEEPGRAM_API_KEY)

    response = await deepgram.transcription.prerecorded(
        {"url": file_url},  
        {"punctuate": True, "model": "nova", "language": "en"},
    )

    transcript = response["results"]["channels"][0]["alternatives"][0]["transcript"]
    return transcript.replace(".", "\\.").replace("!", "\\!")

def transcribe_voice_note_sync_wrapper(file_url):
    return asyncio.run(transcribe_voice_note(file_url))

def process_budget_transcription(chat_id, transcript):
    # Send message to inform user the process has started
    processing_message = "🔄 *Processing your budget...* This may take a few moments."
    escaped_processing_message= processing_message.replace(".", "\\.").replace("!", "\\!").replace("*", "\\*").replace("_", "\\_")
    send_telegram_message(chat_id, escaped_processing_message)
    
    prompt = f"""
You are a highly accurate text parser. Extract the budget categories and amounts from the following statement and return a **strict JSON output**.

### **Example Input:**
"{transcript}"

### **Example Output:**
{{
  "Food": 5000,
  "Travel": 3000,
  "Shopping": 2000
}}

Only return a JSON object with category names as keys and amounts as values.
"""
    model = genai.GenerativeModel("gemini-1.5-pro-latest")
    response = model.generate_content(prompt)
    
    extracted_data = response.text.strip()

    cleaned_json = re.sub(r"```json|```", "", extracted_data).strip()

    try:
        details = json.loads(cleaned_json)
    except json.JSONDecodeError:
        print("Error: Gemini response is not valid JSON")
        return None
    
    store_budget(chat_id, details)

def store_budget(chat_id, extracted_data):
    try:
        # Notify user that the system is storing the budget
        storing_message = "💾 *Storing your budget data...* Please wait."
        escaped_storing_message = storing_message.replace(".", "\\.").replace("!", "\\!").replace("*", "\\*").replace("_", "\\_")
        send_telegram_message(chat_id, escaped_storing_message)

        frappe.logger().info(f"Processing budget storage for chat_id: {chat_id}")

        # Fetch primary account based on Telegram ID
        try:
            primary_account_doc = frappe.get_doc("Primary Account", {"telegram_id": chat_id})
            primary_account_name = primary_account_doc.name
        except Exception as e:
            frappe.logger().error(f"Failed to fetch Primary Account for chat_id {chat_id}: {str(e)}")
            send_telegram_message(chat_id, "❌ *Error:* Unable to fetch account details.")
            return

        frappe.logger().info(f"Primary account found: {primary_account_name}")

        # Fetch existing expense categories
        try:
            existing_categories = frappe.get_all(
                "Expense Category",
                filters={"associated_account_holder": primary_account_name},
                fields=["category_type"]
            )
        except Exception as e:
            frappe.logger().error(f"Error fetching existing categories: {str(e)}")
            send_telegram_message(chat_id, "❌ *Error:* Unable to fetch existing categories.")
            return

        existing_category_list = [cat["category_type"] for cat in existing_categories]
        frappe.logger().info(f"Existing categories for {primary_account_name}: {existing_category_list}")

        updated_categories = []
        non_updated_categories = []

        for category, amount in extracted_data.items():
            try:
                if category in existing_category_list:
                    category_doc = frappe.get_doc("Expense Category", {
                        "category_type": category,
                        "associated_account_holder": primary_account_name
                    })
                    
                    frappe.logger().info(f"Updating budget for category: {category}, Amount: {amount}")

                    category_doc.budget = int(amount)
                    category_doc.save(ignore_permissions=True)
                    updated_categories.append(f"✅ *{category}:* ₹{amount}")
                else:
                    frappe.logger().warning(f"Category not found: {category}")
                    non_updated_categories.append(f"❌ *{category}*")
            except Exception as e:
                frappe.logger().error(f"Error processing category {category}: {str(e)}")

        # Commit changes to database
        try:
            frappe.db.commit()
        except Exception as e:
            frappe.logger().error(f"Database commit failed: {str(e)}")
            send_telegram_message(chat_id, "❌ *Error:* Failed to update the budget in the database.")
            return

        # Send success message
        if updated_categories:
            updated_message = (
                "📊 *Budget Updated Successfully!* 💰\n\n"
                "Your budget has been set for the following categories:\n\n"
                + "\n".join(updated_categories) +
                "\n\n🔹 *You can now track your expenses effectively!* 🚀"
            )
            escaped_updated_message = updated_message.replace(".", "\\.").replace("!", "\\!").replace("*", "\\*").replace("_", "\\_")
            send_telegram_message(chat_id, escaped_updated_message)

        # Send failure message for missing categories
        if non_updated_categories:
            non_updated_message = (
                "⚠️ *Some Categories Were Not Updated* ❌\n\n"
                "The following categories do not exist in your account:\n\n"
                + "\n".join(non_updated_categories) +
                "\n\n🔹 *Please add them first before setting a budget.*"
            )
            escaped_non_updated_message = non_updated_message.replace(".", "\\.").replace("!", "\\!").replace("*", "\\*").replace("_", "\\_")
            send_telegram_message(chat_id, escaped_non_updated_message)

    except Exception as e:
        frappe.logger().error(f"Unexpected error in store_budget: {str(e)}")
        send_telegram_message(chat_id, f"❌ *Error:* Failed to process budget. {str(e)}")

def get_telegram_file_url(file_id):
    bot_token = os.getenv("BOT_TOKEN")
    api_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"

    response = requests.get(api_url).json()

    if response.get("ok"):
        file_path = response["result"]["file_path"]
        return f"https://api.telegram.org/file/bot{bot_token}/{file_path}"

    return None
