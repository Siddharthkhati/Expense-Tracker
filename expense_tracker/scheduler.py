import frappe
from expense_tracker.tasks import send_telegram_message_with_keyboard

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
