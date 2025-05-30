import frappe
import os
import requests
import asyncio
from deepgram import Deepgram
import google.generativeai as genai
from langdetect import detect
import json
import re
import time
import textwrap
from frappe.utils.pdf import get_pdf
from frappe.utils import now_datetime

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

def translate_text_mymemory(text, target_lang='en'):
    if not text.strip():
        return ""
    try:
        source_lang = detect(text)
        if source_lang.lower() == 'en' and target_lang.lower() == 'en':
            return text
        api_url = "https://api.mymemory.translated.net/get"
        params = {
            "q": text,
            "langpair": f"{source_lang}|{target_lang}"
        }
        response = requests.get(api_url, params=params)
        response.raise_for_status()
        translation_data = response.json()
        if "responseData" in translation_data and "translatedText" in translation_data["responseData"]:
            return translation_data["responseData"]["translatedText"]
        elif "errorMessage" in translation_data:
            return ""
        else:
            return ""
    except Exception as e:
        return ""

async def transcribe_audio_async(file_url, chat_id):
    try:
        deepgram = Deepgram(DEEPGRAM_API_KEY)

        send_telegram_message(chat_id, "⏳ *Processing...* 🎙️\n\nHold tight! We're transcribing your audio...".replace(".", "\\.").replace("!", "\\!").replace("_", "\\_"))


        await asyncio.sleep(2)
        message1 = """
Almost Done\\!
"""
        send_telegram_message(chat_id, message1)
        time.sleep(2)

        try:
            response = await deepgram.transcription.prerecorded(
                {"url": file_url},
                {
                    "punctuate": True,
                    "model": "nova-3-general",
                    "detect_language": True
                }
            )
        except Exception as e:
            frappe.log_error(title="Deepgram Transcription Error", message=frappe.get_traceback())
            send_telegram_message(chat_id, "❌ Failed to transcribe audio\\.")
            return None

        try:
            transcript_data = response["results"]["channels"][0]
            alternatives = transcript_data.get("alternatives", [])
            transcript = alternatives[0]["transcript"] if alternatives else ""
            detected_language = transcript_data.get("detected_language", "unknown")
            language_confidence = transcript_data.get("language_confidence", 0)

        except Exception as e:
            frappe.log_error(title="Transcript Extraction Error", message=frappe.get_traceback())
            send_telegram_message(chat_id, "❌ Failed to process transcript\\.")
            return None

        try:
            translated_text = translate_text_mymemory(transcript) 
            escaped_translated = translated_text.replace(".", "\\.").replace("!", "\\!").replace("_", "\\_")
        except Exception as e:
            frappe.log_error(title="Translation Error", message=frappe.get_traceback())
            send_telegram_message(chat_id, "❌ Failed to translate text\\.")
            return None
        
        await asyncio.sleep(2)
        extract_and_notify(translated_text, escaped_translated, chat_id)

        return {
            "original_transcript": transcript,
            "translated_text": translated_text,
            "language": detected_language,
            "confidence": language_confidence
        }

    except Exception as e:
        frappe.log_error(title="Top-Level Transcription Error", message=frappe.get_traceback())
        send_telegram_message(chat_id, f"❌ Error during transcription or translation:\n{str(e)}")
        return None
    
# async def transcribe_audio_async(file_url, chat_id):
#     """Asynchronous function to transcribe audio using Deepgram API."""
#     try:
#         deepgram = Deepgram(DEEPGRAM_API_KEY)

#         response = await deepgram.transcription.prerecorded(
#             {"url": file_url},  # Use direct URL instead of reading the file
#             {"punctuate": True, "model": "nova", "language": "en"},
#         )

#         transcript = response["results"]["channels"][0]["alternatives"][0]["transcript"]

#         escaped_transcript = transcript.replace(".", "\\.").replace("!", "\\!")

#         message = """
#         ⏳ *Processing...* 🎙️  
  
# Hold tight! We're transcribing your audio...   
#         """

#         message = message.replace(".", "\\.").replace("!", "\\!")

#         send_telegram_message(chat_id, message)
#         await asyncio.sleep(2)
#         message1 = """
# Almost Done\!
# """
#         send_telegram_message(chat_id, message1)
#         time.sleep(4)
#         extract_and_notify(transcript, escaped_transcript, chat_id)
#         return transcript

#     except Exception as e:
#         print(f"Error in transcription: {e}")
#         return None

def extract_details_from_text(text):
    """Uses Gemini AI to extract structured details from text."""
    try:
        genai.configure(api_key=GEMINI_API_KEY)

        prompt = f"""
        You are an intelligent expense management assistant.

        Analyze the following user input:
        "{text}"

        Strictly extract and output only these details in JSON format:
        - amount (numeric, float, without currency symbols)
        - category (map specific activities to one of the 9 main categories listed below)
        - merchant (store or service name; if not clear, leave as an empty string "")

        Allowed Categories (only these must appear in the output):
        Food, Transport, Shopping, Healthcare, Education, Entertainment, Bills & Utilities, Savings & Investments, Travel

        Category Mapping Rules (examples):
        - "Dining Out", "Fast Food", "Groceries" → "Food"
        - "Taxi", "Uber", "Train", "Fuel" → "Transport"
        - "Amazon", "Clothing", "Accessories", "Electronics" → "Shopping"
        - "Doctor", "Pharmacy", "Medicine", "Hospital" → "Healthcare"
        - "Tuition", "Books", "Online Course", "Exam Fee" → "Education"
        - "Netflix", "Movies", "Concerts", "Spotify" → "Entertainment"
        - "Rent", "Electricity", "Internet", "Phone", "Water" → "Bills & Utilities"
        - "Mutual Funds", "Stocks", "Savings Account" → "Savings & Investments"
        - "Flight", "Hotel", "Vacation" → "Travel"

        Important Instructions:
        - Only use one of the 9 categories listed above.
        - If the category cannot be determined with reasonable certainty, leave it as an empty string.
        - Return output as PURE JSON only, no extra explanation or text.
        - If any field is missing, leave that key empty (but keep the JSON structure).

        Example Output:
        {{
            "amount": 250.00,
            "category": "Transport",
            "merchant": "Uber"
        }}
        """

        model = genai.GenerativeModel("gemini-1.5-pro-latest")
        response = model.generate_content(prompt)

        extracted_data = response.text.strip()

        print("Raw Gemini Response:", extracted_data)

        cleaned_json = re.sub(r"```json|```", "", extracted_data).strip()

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
        return "Unknown"  

    escape_chars = r"_[]()~`>#+-=|{}.!"
    return re.sub(
        r"([" + re.escape(escape_chars) + r"])", r"\\\1", str(text)
    )  # Ensure conversion to string

def es_markdown_v2(text):
    escape_chars = r'_[]()~`>#+-=|{}.!'
    return ''.join('\\' + char if char in escape_chars else char for char in text)

def extract_and_notify(text, escaped_transcript, chat_id):
    """Extract details from text and send as a Telegram notification."""
    try:
        extracted_details = extract_details_from_text(text)
        if extracted_details:
            amount = escape_markdown_v2(f"{extracted_details.get('amount', 'N/A'):.2f}")
            category = escape_markdown_v2(extracted_details.get("category", "N/A"))
            merchant = escape_markdown_v2(extracted_details.get("merchant") or "Not Specified")

            is_primary = frappe.db.exists("Primary Account", {"telegram_id": chat_id})
            is_family = frappe.db.exists("Family Member", {"telegram_id": chat_id})


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

                        family_escaped_message = family_message.replace(".", "\\.").replace("!", "\\!").replace("_", "\\_")
                        parent_escaped_message = parent_message.replace(".", "\\.").replace("!", "\\!").replace("_", "\\_")

                        send_telegram_message(chat_id, family_escaped_message)
                        send_telegram_message(primary_account_doc.telegram_id, parent_escaped_message)
                        return
                    else:
                        expense_category_name = frappe.get_value(
                            "Expense Category",
                            {
                                "associated_account_holder": primary_account_doc.name,
                                "category_type": category,
                            }
                        )
                        expense_category_type_doc = frappe.get_doc("Expense Category", expense_category_name)
                        
                        amount = float(extracted_details.get("amount", 0.0))
                        if expense_category_type_doc.budget >= amount:
                            expense_category_type_doc.budget -= extracted_details.get("amount", 0.0)
                            expense_category_type_doc.save(ignore_permissions=True)
                            frappe.db.commit()
                        else:
                            message = textwrap.dedent(f"""
                                *Budget Limit Reached*

                                💸 {family_member_doc.full_name} tried to spend ₹{amount:.2f} in the *{category}* category,
                                but the remaining budget is only ₹{expense_category_type_doc.budget:.2f}.

                                ⚠️ This transaction has been declined to maintain control over shared expenses.

                                🔔 Consider topping up the category budget or discussing spending priorities.
                            """)

                            dependent_message = textwrap.dedent(f"""
                                *Transaction Declined*

                                Unfortunately, your attempt to spend ₹{amount:.2f} in *{category}* was not successful. 
                                The remaining budget is only ₹{expense_category_type_doc.budget:.2f}.
                            """)
                            send_telegram_message(chat_id, es_markdown_v2(dependent_message))
                            send_telegram_message(primary_account_doc.telegram_id, es_markdown_v2(message))
                            return
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
                        escaped_message = es_markdown_v2(warning_message)
                        send_telegram_message(chat_id, escaped_message)
                        return
                    else:
                        expense_category_name = frappe.get_value(
                            "Expense Category",
                            {
                                "associated_account_holder": primary_account_doc.name,
                                "category_type": category,
                            }
                        )
                        expense_category_type_doc = frappe.get_doc("Expense Category", expense_category_name)

                        amount = float(extracted_details.get("amount", 0.0))
                        if expense_category_type_doc.budget >= amount:
                            expense_category_type_doc.budget -= amount
                            expense_category_type_doc.save(ignore_permissions=True)
                            frappe.db.commit()
                        else:
                            message =  textwrap.dedent(f"""
                                *Budget Limit Alert*

                                ✨ You attempted to spend ₹{amount:.2f} in the *{category}* category,
                                but your available budget is only ₹{expense_category_type_doc.budget:.2f}.

                                📉 *Transaction Declined* to help you stay within your personalized spending limits.

                                💬 Need more flexibility? Tap into your financial plan or request a balance update.
                            """)
                            send_telegram_message(chat_id, es_markdown_v2(message))
                            return
                except Exception as e:
                    frappe.log_error(f"Error processing primary account transaction: {str(e)}")

            if is_primary:
                try:
                    primary_account = frappe.get_doc("Primary Account", {"telegram_id": chat_id})
                    if primary_account.salary >= extracted_details.get("amount", 0.0):
                        primary_account.salary -= extracted_details.get("amount", 0.0)
                        primary_account.save(ignore_permissions=True)
                        frappe.db.commit()
                    else:
                        expense_category_name = frappe.get_value(
                            "Expense Category",
                            {
                                "associated_account_holder": primary_account.name,
                                "category_type": category,
                            }
                        )
                        expense_category_type_doc = frappe.get_doc("Expense Category", expense_category_name)
                        
                        expense_category_type_doc.budget += extracted_details.get("amount", 0.0)
                        expense_category_type_doc.save(ignore_permissions=True)
                        frappe.db.commit()

                        keyboard_pm = [
                            [{"text": "💰 Check Balance", "callback_data": "check_balance"}],
                            [{ "text": "➕ Add Money", "callback_data": "add_money"}]
                        ]
                        
                        send_telegram_message_with_keyboard(chat_id, es_markdown_v2("⚠️ *Insufficient Balance!* Please check your account."), keyboard_pm)
                        return
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
                        primary_account_holder_id = family_member.primary_account_holder

                        expense_category_name = frappe.get_value(
                            "Expense Category",
                            {
                                "associated_account_holder": primary_account_holder_id,
                                "category_type": category,
                            }
                        )
                        expense_category_type_doc = frappe.get_doc("Expense Category", expense_category_name)
                        
                        expense_category_type_doc.budget += extracted_details.get("amount", 0.0)
                        expense_category_type_doc.save(ignore_permissions=True)
                        frappe.db.commit()
                        keyboard_fm = [
                            [{"text": "💰 Check Balance", "callback_data": "check_balance"}],
                            [{ "text": "🛎️ Request Money", "callback_data": "request_money"}]
                        ]
                        
                        send_telegram_message_with_keyboard(chat_id, es_markdown_v2("⚠️ *Insufficient pocket money!* Please request more funds."), keyboard_fm)
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
💡 *Expense Summary* 💡\n\n
💰 *Amount:* {amount}  \n
📂 *Category:* {category}  \n
🏪 *Merchant:* {merchant}  \n\n
✅ *Your expense has been successfully recorded\.*\n\n
📊 _Stay on top of your finances with effortless tracking\!_ \n            

"""

            try:
                if is_primary:
                    account_doc = frappe.get_doc("Primary Account", {"telegram_id": chat_id})
                    account_name = account_doc.name
                elif is_family:
                    account_doc = frappe.get_doc("Family Member", {"telegram_id": chat_id})
                    account_name = account_doc.primary_account_holder

                expense = frappe.get_doc(
                    {
                        "doctype": "Expense",
                        "account_holder": account_name,
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
            send_telegram_message(chat_id, "Unable to extract details\. Please try again or contact the admin for help\.")
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
            frappe.log_error(
                f"Failed to send Telegram notification to chat ID {chat_id}: {response_data}",
                "Telegram Send Error"
            )
    except Exception as e:
        frappe.log_error(f"Error sending Telegram message to chat ID {chat_id}: {str(e)}", "Telegram Send Error")



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

    except Exception as e:
        frappe.log_error(f"Error sending Telegram message: {str(e)}")

def send_pdf_to_telegram(chat_id, file_path):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
    
    with open(file_path, "rb") as f:
        files = {"document": f}
        data = {"chat_id": chat_id}
        response = requests.post(url, data=data, files=files)
    
    if not response.ok:
        frappe.log_error(response.text, "Telegram PDF Send Error")

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
                message = "Please enter your *Account ID* to continue."
            elif callback_data == "role_dependent":
                frappe.cache.set_value(f"callback_{chat_id}", callback_data)
                message = "Please enter your *Account ID* to continue."
            elif callback_data == "check_balance":
                message = get_balance(chat_id)
            elif callback_data == "add_money":
                frappe.cache.set_value(f"callback_{chat_id}", callback_data)
                message = "➕ *Enter the amount you want to add.*"
            elif callback_data == "request_money":
                frappe.cache.set_value(f"callback_{chat_id}", callback_data)
                message = "💸 *Enter the amount you want to request.*"
            elif callback_data == "view_report":
                generate_and_send_report(chat_id)
            if callback_data == "set_monthly_budget":
                frappe.cache.set_value(f"set_budget_{chat_id}", True)
                message = """
🎙️ *Set your monthly category budgets using a voice message!*  
Just speak naturally — for example:  
"_Set Food to ₹5000, Travel ₹3000, and Shopping ₹2000_"  
or  
"_Food ₹5000, Travel ₹3000, Shopping ₹2000_"

We'll automatically update your budgets accordingly ✅
"""

            elif callback_data == "approve":
                approve_money_request(chat_id)
                return {"ok": True}
            elif callback_data == "deny":
                deny_money_request(chat_id)
                return {"ok": True}
            elif callback_data == "confirm_delete_auto_expense":
                confirm_delete_auto_expense_handler(chat_id)
                return {"ok": True}
            
            elif callback_data == "cancel_delete_auto_expense":
                cancel_delete_auto_expense_handler(chat_id)
                return {"ok": True}
            
            escaped_message = (
                message.replace(".", "\\.")
                .replace("!", "\\!")
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
                    "👨‍👩‍👧‍👦 *Are you a Primary Member or a Dependent?*"
                )

                keyboard = [
                    [{"text": "👨‍👩‍👦 Primary", "callback_data": "role_parent"}],
                    [{"text": "🧑‍🎓 Dependent", "callback_data": "role_dependent"}],
                ]

                escaped_message = (
                    welcome_message.replace(".", "\\.")
                    .replace("!", "\\!")
                    .replace("_", "\\_")
                )
                send_telegram_message_with_keyboard(chat_id, escaped_message, keyboard)

            elif text == "/set_auto_expense":
                if frappe.db.exists("Primary Account", {"telegram_id": chat_id}):
                    auto_expense_message = textwrap.dedent("""
                        🎤 *Auto-Log Your Recurring Expense*  
                        Just send a voice note with the details.

                        For example:  
                        "Log my rent of $500 every month under the Rent category."

                        Please mention:  
                        • Category  
                        • Amount  
                        • Frequency (e.g., Monthly, Weekly)

                        We'll take care of the rest — automatically. ✨
                    """)

                    escaped_message = es_markdown_v2(auto_expense_message)
                    send_telegram_message(chat_id, escaped_message)
                    frappe.cache().set_value(f"set_auto_expense_{chat_id}", True)
                    return
                else:
                    send_telegram_message(chat_id, es_markdown_v2("❌ This feature isn’t available on your account.\nIf you think this is a mistake, feel free to reach out to our team."))
                    return
            
            elif text == "/delete_auto_expense":
                if frappe.db.exists("Primary Account", {"telegram_id": chat_id}):
                    confirm_message = textwrap.dedent("""
                        ⚠️ *Delete Auto Expense?*

                        This will permanently stop all scheduled recurring expenses from being auto-logged.

                        Are you sure you want to proceed?
                    """)

                    escaped_message = es_markdown_v2(confirm_message)

                    confirm_keyboard = [
                        [{"text": "✅ Confirm", "callback_data": "confirm_delete_auto_expense"}],
                        [{"text": "❌ Cancel", "callback_data": "cancel_delete_auto_expense"}],
                    ]
                    frappe.cache.set_value(f"delete_auto_expense_{chat_id}", True)
                    
                    send_telegram_message_with_keyboard(chat_id, escaped_message, confirm_keyboard)
                    return
                else:
                    send_telegram_message(chat_id, es_markdown_v2("❌ This feature isn’t available on your account.\nIf you think this is a mistake, feel free to reach out to our team."))
                    return


            elif "voice" in data["message"]:
                if frappe.cache.get_value(f"set_budget_{chat_id}"):
                    voice_file_id = data["message"]["voice"]["file_id"]
                    file_url = get_telegram_file_url(voice_file_id)

                    transcript = transcribe_voice_note_sync_wrapper(file_url)
                    process_budget_transcription(chat_id, transcript)
                    frappe.cache.delete_value(f"set_budget_{chat_id}")
                    return
                
                if frappe.cache.get_value(f"set_auto_expense_{chat_id}"):
                    voice_file_id = data["message"]["voice"]["file_id"]
                    file_url = get_telegram_file_url(voice_file_id)

                    transcript = transcribe_voice_note_sync_wrapper(file_url)
                    process_auto_expense_transcription(chat_id, transcript)
                    frappe.cache.delete_value(f"set_auto_expense_{chat_id}")
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
                    escaped_ai_response = ai_response.replace(".", "\\.").replace("!", "\\!").replace("_", "\\_")

                    send_telegram_message(chat_id, escaped_ai_response)
                else:
                    if user_role == "role_parent" or user_role == "role_dependent":
                        parent_exists = frappe.db.exists("Primary Account", text)

                        if not parent_exists:
                            message = "❌ Invalid Account ID. Please try again."
                            escaped_message = (
                                message.replace(".", "\\.")
                                .replace("!", "\\!")
                                .replace("_", "\\_")
                            )
                            send_telegram_message(chat_id, escaped_message)
                            return {"ok": False, "error": "Invalid Parent ID"}

                        if user_role == "role_parent":
                            if frappe.db.exists("Primary Account", {"telegram_id": chat_id}):
                                message = "✅ *You're already registered!* Start tracking your expenses now. 📊"
                                escaped_message = (
                                    message.replace(".", "\\.")
                                    .replace("!", "\\!")
                                    .replace("_", "\\_")
                                )
                                send_telegram_message(chat_id, escaped_message)
                                frappe.cache().delete_value(f"callback_{chat_id}")
                                return {"ok": True} 

                            message = textwrap.dedent("""
                                👋 You're now verified as the *Primary Account Holder*.

                                Here’s what you can do directly from Telegram:

                                🔹 *Log Expenses Instantly* using voice commands  
                                🔹 *Check Your Balance* and *Add Money* seamlessly  
                                🔹 *Receive Weekly Summaries* of your spending  
                                🔹 *Set Monthly Budgets* by category via voice  
                                🔹 *Auto-Log Recurring Expenses* by sending `/set_auto_expense`
                                🔹 *Delete Auto Expenses* anytime using `/delete_auto_expense`
                                🔹 *Get Notified* if a dependent tries to log expenses in unapproved categories  

                                To explore complete insights, manage your dependents, and configure categories:  
                                🌐 [Access Your Dashboard](https://two-korecent.frappe.cloud/app/dashboard-view/My%20Activity)

                                Stay in control — effortlessly.
                            """)

                            escaped_message = es_markdown_v2(message)

                            primary_account_doc = frappe.get_doc("Primary Account", text)
                            primary_account_doc.telegram_id = chat_id  
                            primary_account_doc.save(ignore_permissions=True)
                            frappe.db.commit()

                            send_telegram_message(chat_id, escaped_message)

                        elif user_role == "role_dependent":
                            if frappe.db.exists("Family Member", {"telegram_id": chat_id}):
                                message = "✅ *You're already registered!* Start tracking your expenses now. 📊"
                                escaped_message = (
                                    message.replace(".", "\\.")
                                    .replace("!", "\\!")
                                    .replace("_", "\\_")
                                )
                                send_telegram_message(chat_id, escaped_message)
                                frappe.cache().delete_value(f"callback_{chat_id}")
                                return {"ok": True} 

                            else:
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

                                message = textwrap.dedent("""
                                    🎉 *You are verified as a Dependent!*

                                    Here’s what you can do directly from Telegram:

                                    🔹 *Add Your Expenses* using voice commands  
                                    🔹 *View Your Expense History* anytime  
                                    🔹 *Receive Weekly Reports* of your spending  
                                    🔹 *Get Reminders* to stay within your budget limits  
                                    🔹 *Be Notified* if an expense is blocked due to category restrictions

                                    Stay on top of your spending — all within Telegram.
                                """)
                                escaped_message = es_markdown_v2(message)
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
                            return {"ok": False, "error": "Invalid amount"}

                        escaped_message = message.replace(".", "\\.").replace("!", "\\!").replace("_", "\\_")
                        send_telegram_message(chat_id, escaped_message)

                    elif user_role == "request_money":
                        if text.isdigit():
                            amount = int(text)

                            try:
                                family_member_doc = frappe.get_doc("Family Member", {"telegram_id": chat_id})
                            except frappe.DoesNotExistError:
                                warning_message = "❌ *Error:* You are not registered as a family member."
                                escaped_message = warning_message.replace(".", "\\.").replace("!", "\\!").replace("_", "\\_")
                                send_telegram_message(chat_id, escaped_message)
                                return {"ok": False, "error": "Family Member not found"}

                            try:
                                primary_account_doc = frappe.get_doc("Primary Account", family_member_doc.primary_account_holder)
                            except frappe.DoesNotExistError:
                                warning_message = "❌ *Error:* Your parent account does not exist."
                                escaped_message = warning_message.replace(".", "\\.").replace("!", "\\!").replace("_", "\\_")
                                send_telegram_message(chat_id, escaped_message)
                                return {"ok": False, "error": "Parent Account not found"}

                            if not primary_account_doc.telegram_id:
                                warning_message = "❌ *Error:* Parent Telegram ID is missing."
                                escaped_message = warning_message.replace(".", "\\.").replace("!", "\\!").replace("_", "\\_")
                                send_telegram_message(chat_id, escaped_message)
                                return {"ok": False, "error": "Parent Telegram ID missing"}

                            frappe.cache.set_value(f"request_amount_{primary_account_doc.telegram_id}", amount)
                            frappe.cache.set_value(f"request_parent_{primary_account_doc.telegram_id}", chat_id)

                            # Notify dependent
                            success_message = f"⏳ *Request Sent!* ₹{amount} has been requested from your parent.\nWe will notify you once they respond. ✅"
                            escaped_message = success_message.replace(".", "\\.").replace("!", "\\!").replace("_", "\\_")
                            send_telegram_message(chat_id, escaped_message)

                            # Notify parent with options
                            parent_message = f"📢 *Money Request Alert!*\nYour dependent *{family_member_doc.full_name}* has requested ₹{amount}.\nWould you like to approve it?"
                            parent_escaped_message = parent_message.replace(".", "\\.").replace("!", "\\!").replace("_", "\\_")

                            keyboard = [
                                [{"text": "✅ Approve", "callback_data": "approve"}],
                                [{"text": "❌ Deny", "callback_data": "deny"}],
                            ]

                            send_telegram_message_with_keyboard(primary_account_doc.telegram_id, parent_escaped_message, keyboard)

                        else:
                            warning_message = "⚠️ *Invalid amount.* Please enter a valid number."
                            escaped_message = warning_message.replace(".", "\\.").replace("!", "\\!").replace("_", "\\_")
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

        parent_escaped_message = parent_message.replace(".", "\\.").replace("!", "\\!").replace("_", "\\_")
        dependent_escaped_message = dependent_message.replace(".", "\\.").replace("!", "\\!").replace("_", "\\_")

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

    parent_escaped_message = parent_message.replace(".", "\\.").replace("!", "\\!").replace("_", "\\_")
    dependent_escaped_message = dependent_message.replace(".", "\\.").replace("!", "\\!").replace("_", "\\_")

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

@frappe.whitelist()
def process_budget_transcription(chat_id, transcript):
    message1 = (
    "⏳ *Hold Tight!* We're analyzing your voice command and preparing your budget summary.\n\n"
    "This will only take a moment. 💡"
)

    send_telegram_message(chat_id, es_markdown_v2(message1))

    prompt = f"""
You are a highly accurate text parser. Extract the budget categories and their corresponding amounts from the following user input. Return the result as a **single JSON object**. The keys of the JSON object should be the budget categories, and the values should be the amounts as integers.

**User Input:**
"{transcript}"

**Example Output:**
{{
  "Food": 5000,
  "Travel": 3000,
  "Shopping": 2000
}}

Ensure that the output is strictly a valid JSON object and nothing else. If no budget information can be extracted, return an empty JSON object: {{}}.
"""
    try:
        model = genai.GenerativeModel("gemini-1.5-pro-latest")
        response = model.generate_content(prompt)
        extracted_data_str = response.text.strip()

        try:
            details = json.loads(extracted_data_str)
        except json.JSONDecodeError:
            cleaned_json = re.sub(r"```json|```", "", extracted_data_str).strip()
            try:
                details = json.loads(cleaned_json)
            except json.JSONDecodeError as e:
                send_telegram_message(chat_id, es_markdown_v2("❌ *Error:* Couldn't understand your budget. Try again with clear categories and amounts."))
                return
        
        time.sleep(4)
        store_budget(chat_id, details)

    except Exception as e:
        frappe.log_error(f"Error during Gemini processing: {e}", "Budget Transcription")
        send_telegram_message(chat_id, es_markdown_v2("❌ *Error:* There was an issue processing your request. Please try again later."))


@frappe.whitelist()
def store_budget(chat_id, extracted_data):
    message2 = (
    "📊 *Processing your voice command...*\n\n"
    "Setting up your budgets — just a moment. 🚀"
)
    send_telegram_message(chat_id, es_markdown_v2(message2))
    
    time.sleep(2)

    try:
        primary_account_name = frappe.db.get_value("Primary Account", {"telegram_id": chat_id}, "name")
        if not primary_account_name:
            send_telegram_message(chat_id, "❌ *Error:* Unable to fetch account details.")
            return

        existing_categories = frappe.get_all(
            "Expense Category",
            filters={"associated_account_holder": primary_account_name},
            fields=["category_type"]
        )
        existing_category_list = [cat["category_type"].lower() for cat in existing_categories]

        updated_categories = []
        non_updated_categories = []

        for category, amount in extracted_data.items():
            if category.lower() in existing_category_list:
                try:
                    frappe.db.set_value(
                        "Expense Category",
                        {"category_type": category, "associated_account_holder": primary_account_name},
                        "budget",
                        int(amount),
                        update_modified=True,
                    )
                    updated_categories.append(f"🔹 *{es_markdown_v2(category)}:* ₹{amount}")
                except Exception as e:
                    frappe.log_error(f"Error updating budget for {category}: {e}", "Budget Storage")
            else:
                non_updated_categories.append(f"🔹 *{es_markdown_v2(category)}*")

        try:
            frappe.db.commit()
        except Exception as e:
            frappe.log_error(f"Database commit failed: {e}", "Budget Storage")
            send_telegram_message(chat_id, "❌ *Error:* Failed to update the budget in the database.")
            return

        if updated_categories:
            message = (
                "📊 *Budget Updated Successfully!* 💰\n\n"
                "Your budget has been set for the following categories:\n\n"
                + "\n".join(updated_categories) +
                "\n\n*You can now track your expenses effectively!* 🚀"
            )
            send_telegram_message(chat_id, es_markdown_v2(message))

        if non_updated_categories:
            message = (
                "⚠️ *Some Categories Were Not Updated* ❌\n\n"
                "The following categories do not exist in your account:\n\n"
                + "\n".join(non_updated_categories) +
                "\n\n*Please add them first before setting a budget.*"
            )
            send_telegram_message(chat_id, es_markdown_v2(message))

    except Exception as e:
        frappe.log_error(f"Unexpected error in store_budget: {e}")
        send_telegram_message(chat_id, es_markdown_v2(f"❌ *Error:* Failed to process budget. {str(e)}"))

@frappe.whitelist()
def process_auto_expense_transcription(chat_id, transcript):
    message1 = (
        "⏳ *Hold Tight!* We're analyzing your voice command and preparing your recurring expense details.\n\n"
        "This will only take a moment. 💡"
    )

    send_telegram_message(chat_id, es_markdown_v2(message1))

    prompt = f"""
    You are an intelligent recurring expense management assistant.

    Analyze the following user command:
    "{transcript}"

    Your task is to extract the following fields from the input for automatic recurring expense logging:

    Output a JSON object with the following keys:
    - amount (numeric float, without currency symbols)
    - category (must strictly match one of the 9 predefined categories below)
    - merchant (store, landlord, or service name; if not clear, leave as an empty string "")
    - frequency (set to "monthly" unless the user specifies otherwise like "weekly", "bimonthly", "biweekly", "yearly")

    Allowed Categories (choose the most appropriate one):
    Food, Transport, Shopping, Healthcare, Education, Entertainment, Bills & Utilities, Savings & Investments, Travel

    Category Mapping Rules (examples):
    - "Rent", "Home Rent", "House Rent" → Bills & Utilities
    - "Groceries", "Dining", "Fast Food" → Food
    - "Flight", "Hotel", "Trip", "Vacation" → Travel
    - "Netflix", "Subscription", "Movies", "Spotify" → Entertainment
    - "Tuition", "Books", "Courses" → Education
    - "Medicine", "Hospital", "Pharmacy" → Healthcare
    - "Fuel", "Taxi", "Uber", "Train" → Transport
    - "Amazon", "Clothing", "Shopping", "Gadgets" → Shopping
    - "SIP", "Mutual Fund", "Stocks", "Investment" → Savings & Investments

    Important:
    - Use only one of the 9 allowed categories.
    - If the frequency is not explicitly mentioned, default to "monthly".
    - If the merchant is not clear, leave the field as an empty string "".
    - Return response strictly as pure JSON with no extra text or explanation.

    Example Output:
    {{
        "amount": 10000.0,
        "category": "Bills & Utilities",
        "merchant": ""
        "frequency": "monthly"
    }}
    """ 

    try:
        model = genai.GenerativeModel("gemini-1.5-pro-latest")
        response = model.generate_content(prompt)
        extracted_data_str = response.text.strip()

        try:
            details = json.loads(extracted_data_str)
        except json.JSONDecodeError:
            cleaned_json = re.sub(r"```json|```", "", extracted_data_str).strip()
            try:
                details = json.loads(cleaned_json)
            except json.JSONDecodeError as e:
                send_telegram_message(chat_id, es_markdown_v2("❌ *Error:* Couldn't understand your recurring expense. Try again with clear category, amount, and frequency details."))
                return

        time.sleep(4)
        store_auto_expense(chat_id, details)

    except Exception as e:
        frappe.log_error(f"Error during Gemini processing: {e}", "Auto Expense Transcription")
        send_telegram_message(chat_id, es_markdown_v2("❌ *Error:* There was an issue processing your request. Please try again later."))

def store_auto_expense(chat_id, details):
    if details:
        category = details.get("category")
        amount = details.get("amount")
        frequency = details.get("frequency")
        merchant = escape_markdown_v2(details.get("merchant") or "Not Specified")
        
        if category and amount and frequency:
            primary_account = frappe.get_doc("Primary Account", {"telegram_id": chat_id})
            user_id = primary_account.name if primary_account else None

            if not user_id:
                send_telegram_message(chat_id, es_markdown_v2("❌ *Account not found.* Please ensure your account is verified to continue."))
                return

            valid_categories = frappe.get_all("Expense Category", filters={"associated_account_holder": primary_account.name}, fields=["category_type"])

            valid_category_names = [category_doc.get("category_type") for category_doc in valid_categories]

            if category not in valid_category_names:
                send_telegram_message(chat_id, es_markdown_v2(f"❌ *The category '{category}' is not valid for your account.* Please choose from the available categories."))
                return
            
            expense_doc = frappe.get_doc({
                "doctype": "Recurring Expense",
                "user_id": user_id,
                "telegram_id": chat_id,
                "category": category,
                "amount": amount,
                "merchant": merchant,
                "frequency": frequency,
                "is_active": 1,  
            })

            expense_doc.insert(ignore_permissions=True)
            frappe.db.commit()

            send_telegram_message(chat_id, es_markdown_v2(
                f"✅ *Recurring expense added successfully!*\n\n"
                f"• *Category:* {category}\n"
                f"• *Amount:* {amount}\n"
                f"• *Merchant:* {merchant}\n"
                f"• *Frequency:* {frequency}"
            ))
        else:
           send_telegram_message(chat_id, es_markdown_v2("❌ *Sorry,* we couldn't process your request due to missing or incomplete information. Please try again with clear details."))

def confirm_delete_auto_expense_handler(chat_id):

    if not frappe.cache.get_value(f"delete_auto_expense_{chat_id}"):
        return
    
    recurring_expenses = frappe.get_all(
        "Recurring Expense",
        filters={"telegram_id": chat_id},
        fields=["name"]
    )

    if recurring_expenses:
        for exp in recurring_expenses:
            frappe.delete_doc("Recurring Expense", exp.name, ignore_permissions=True)
        frappe.db.commit()

        message = textwrap.dedent("""
            ✅ *Auto Expenses Deleted Successfully!*  
            All your scheduled recurring expenses have been removed.

            You can set them again anytime using `/set_auto_expense`.
        """)
    else:
        message = textwrap.dedent("""
            ℹ️ *No Auto Expenses Found!*  
            You don’t have any recurring expenses set up at the moment.
        """)

    frappe.cache.delete_value(f"delete_auto_expense_{chat_id}")
    escaped_message = es_markdown_v2(message)
    send_telegram_message(chat_id, escaped_message)

def cancel_delete_auto_expense_handler(chat_id):
    if not frappe.cache.get_value(f"delete_auto_expense_{chat_id}"):
        return
    
    message = textwrap.dedent("""
        ❌ *Deletion Cancelled!*  
        Your recurring expenses are safe and will continue as scheduled.
    """)

    frappe.cache.delete_value(f"delete_auto_expense_{chat_id}")
    escaped_message = es_markdown_v2(message)
    send_telegram_message(chat_id, escaped_message)

def generate_and_send_report(chat_id):
    try:
        current_year = frappe.utils.now_datetime().year

        report = frappe.get_doc("Report", "Expense Summary")  # Your report name
        columns, data = report.get_data(filters={"chat_id": chat_id})

        html = frappe.render_template("expense_tracker/templates/pages/expense_report_template.html", {
            "columns": columns,
            "data": data,
            "year": current_year
        })

        pdf = frappe.utils.pdf.get_pdf(html)

        file_path = f"/tmp/expense_report_{chat_id}.pdf"
        with open(file_path, "wb") as f:
            f.write(pdf)

        if hasattr(frappe, 'send_pdf_to_telegram'):
            frappe.send_pdf_to_telegram(chat_id, file_path)
        else:
            frappe.log_error("send_pdf_to_telegram function not found.", "Report Generation")

        import os
        os.remove(file_path)

    except Exception as e:
        frappe.log_error(frappe.as_json(e), "Report Generation Error")
        frappe.msgprint(f"An error occurred while generating the report: {e}", indicator='error')

def get_telegram_file_url(file_id):
    bot_token = os.getenv("BOT_TOKEN")
    api_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"

    response = requests.get(api_url).json()

    if response.get("ok"):
        file_path = response["result"]["file_path"]
        return f"https://api.telegram.org/file/bot{bot_token}/{file_path}"

    return None
