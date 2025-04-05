import re
import frappe
from datetime import datetime, timedelta
from expense_tracker.tasks import send_telegram_message_with_keyboard, send_telegram_message

@frappe.whitelist(allow_guest=True)
def monthly_add_money_reminder():
    primary_accounts = frappe.get_all("Primary Account", fields=["telegram_id", "full_name"])

    for account in primary_accounts:
        chat_id = account["telegram_id"]
        full_name = account["full_name"]

        message = f"""
        🔔 *Monthly Budget Reminder* 🔔  

        Hello {full_name},  
        It's the start of a new month! 🚀  
        Please ensure your budget is updated to manage your expenses smoothly.  

        ➕ Tap below to set your budget for this month! 👇
        """

        keyboard = [
            [{"text": "📊 Set Monthly Budget", "callback_data": "set_monthly_budget"}]
        ]
        
        escaped_message = message.replace(".", "\\.").replace("!", "\\!").replace("*", "\\*").replace("_", "\\_")
        send_telegram_message_with_keyboard(chat_id, escaped_message, keyboard)
        frappe.logger().info(f"Sent reminder to {full_name} ({chat_id})")

    frappe.logger().info("Monthly Budget Reminder completed.")
    return {"status": "success", "message": "Reminders sent to all users."}

@frappe.whitelist(allow_guest=True)
def send_weekly_parent_spending_summary():
    try:
        today_india = datetime.now()  # Get current time in India

        # Calculate last week's start and end dates based on India's time
        last_week_start_india = today_india - timedelta(days=today_india.weekday() + 7)
        last_week_end_india = last_week_start_india + timedelta(days=6)

        frappe.log_error(f"Weekly Spending Summary (India Time): Today: {today_india.strftime('%Y-%m-%d %H:%M:%S')}", "Weekly Spending Summary")
        frappe.log_error(f"Weekly Spending Summary (India Time): Last Week Start: {last_week_start_india.strftime('%Y-%m-%d %H:%M:%S')}, End: {last_week_end_india.strftime('%Y-%m-%d %H:%M:%S')}", "Weekly Spending Summary")

        primary_accounts = frappe.get_all("Primary Account", fields=["telegram_id", "name"])
        frappe.log_error(f"Weekly Spending Summary: Primary Accounts fetched: {primary_accounts}", "Weekly Spending Summary")

        for account in primary_accounts:
            chat_id = account["telegram_id"]
            account_name = account["name"]
            frappe.log_error(f"Weekly Spending Summary: Processing account: {account_name}, Telegram ID: {chat_id}", "Weekly Spending Summary")

            expenses = frappe.db.sql("""
                SELECT category, SUM(amount) as total_spent
                FROM `tabExpense`
                WHERE user_id = %s
                AND `date` BETWEEN %s AND %s
                GROUP BY category
            """, (chat_id, last_week_start_india.strftime('%Y-%m-%d 00:00:00'), last_week_end_india.strftime('%Y-%m-%d 23:59:59')), as_dict=True)
            frappe.log_error(f"Weekly Spending Summary: Expenses for {chat_id}: {expenses}", "Weekly Spending Summary")

            if not expenses:
                frappe.log_error(f"Weekly Spending Summary: No expenses found for {account_name} (Telegram ID: {chat_id}) for the period {last_week_start_india.strftime('%Y-%m-%d')} to {last_week_end_india.strftime('%Y-%m-%d')}.", "Weekly Spending Summary")
                continue

            spending_details = "\n".join([f"📌 *{expense['category']}*: ₹{expense['total_spent']}" for expense in expenses])

            message = f"""
📊 *Weekly Spending Summary* 📅
🔹 *Period:* {last_week_start_india.strftime('%d %b %Y')} - {last_week_end_india.strftime('%d %b %Y')}

💰 *Here's what you spent in each category:*
{spending_details}

🔹 *Keep track and plan ahead for next week!* 🚀
            """

            escaped_message = escape_markdown(message)
            try:
                send_telegram_message(chat_id, escaped_message)
                frappe.log_error(f"Weekly Spending Summary: Telegram message sent successfully to {account_name} (Telegram ID: {chat_id})", "Weekly Spending Summary")
            except Exception as telegram_e:
                frappe.log_error(f"Weekly Spending Summary: Error sending Telegram message to {account_name} (Telegram ID: {chat_id}): {str(telegram_e)}", "Weekly Spending Summary")

        frappe.db.commit()
        frappe.log_error(f"Weekly Spending Summary: Execution completed successfully.", "Weekly Spending Summary")

    except Exception as e:
        frappe.log_error(f"Weekly Spending Summary: An unexpected error occurred: {str(e)}", "Weekly Spending Summary")

@frappe.whitelist(allow_guest=True)
def send_weekly_family_spending_summary():
    try:
        today = datetime.today()
        last_week_start = today - timedelta(days=today.weekday() + 7)
        last_week_end = last_week_start + timedelta(days=6)

        family_members = frappe.get_all("Family Member", fields=["telegram_id", "name"])

        for member in family_members:
            chat_id = member["telegram_id"]
            member_id = member["name"]

            member_name = frappe.get_doc("Family Member", member_id)

            expenses = frappe.db.sql("""
                SELECT category, SUM(amount) as total_spent
                FROM `tabExpense`
                WHERE user_id = %s
                AND date BETWEEN %s AND %s
                GROUP BY category
            """, (chat_id, last_week_start.strftime('%Y-%m-%d'), last_week_end.strftime('%Y-%m-%d')), as_dict=True)

            if not expenses:
                continue

            spending_details = "\n".join([f"📌 *{expense['category']}*: ₹{expense['total_spent']}" for expense in expenses])

            message = f"""
👨‍👩‍👦 *Weekly Spending Summary* 🧾  
👤 *User:* {member_name}  
🔹 *Period:* {last_week_start.strftime('%d %b %Y')} - {last_week_end.strftime('%d %b %Y')}  

💰 *Here's what you spent in each category:*  
{spending_details}  

            """

            escaped_message = escape_markdown(message)

            send_telegram_message(chat_id, escaped_message)

        frappe.db.commit()

    except Exception as e:
        frappe.log_error(f"Error in Weekly Family Spending Summary: {str(e)}", "Family Spending Summary")

def escape_markdown(text):
    escape_chars = r"[_*[\]()~`>#+\-=|{}.!]"
    return re.sub(f"([{escape_chars}])", r"\\\1", text)