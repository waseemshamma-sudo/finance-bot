import os
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from dotenv import load_dotenv
from datetime import datetime
import re

# تحميل المتغيرات من ملف .env
load_dotenv(r"C:\Users\Admin\finance\.env")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("❌ لم يتم العثور على TELEGRAM_BOT_TOKEN في ملف البيئة")

# حالات المحادثة
ADD_EXPENSE, ADD_INCOME, TRANSFER, NEW_ACCOUNT, CATEGORY = range(5)
EXCEL_FILE = "financial_tracker.xlsx"

# دالة جديدة للتعامل مع أسماء الحسابات مع الإيموجي
def get_account_name(user_input, accounts_df):
    """
    البحث عن اسم الحساب مع أو بدون الإيموجي
    """
    # إزالة الإيموجي من أسماء الحسابات للبحث
    accounts_without_emoji = []
    for account_name in accounts_df['اسم الحساب']:
        # إزالة جميع الأحرف غير الأبجدية والمسافات
        cleaned_name = re.sub(r'[^\w\s]', '', account_name).strip()
        accounts_without_emoji.append(cleaned_name)
    
    # البحث عن الحساب بدون الإيموجي
    for i, account_name in enumerate(accounts_without_emoji):
        if user_input.strip() in account_name:
            return accounts_df.iloc[i]['اسم الحساب']
    
    # إذا لم يتم العثور، البحث بالإيموجي
    for account_name in accounts_df['اسم الحساب']:
        if user_input.strip() in account_name:
            return account_name
    
    return None

# دالة جديدة لإنشاء قائمة الحسابات بدون إيموجي
def get_accounts_without_emoji(accounts_df):
    """إرجاع قائمة الحسابات بدون إيموجي"""
    accounts_list = []
    for _, acc in accounts_df.iterrows():
        account_name = acc['اسم الحساب']
        # إزالة الإيموجي
        cleaned_name = re.sub(r'[^\w\s]', '', account_name).strip()
        accounts_list.append("• " + cleaned_name)
    return "\n".join(accounts_list)

# تهيئة ملف Excel إذا لم يكن موجوداً
def init_excel_file():
    if not os.path.exists(EXCEL_FILE):
        with pd.ExcelWriter(EXCEL_FILE) as writer:
            accounts_data = {
                'اسم الحساب': ['💳 البنك الأهلي', '💳 بطاقة الائتمان', '💵 النقدي', '📃 ديون على الآخرين'],
                'النوع': ['بنك', 'بطاقة ائتمان', 'نقدي', 'دين'],
                'الرصيد': [10000, 5000, 2000, 3000]
            }
            pd.DataFrame(accounts_data).to_excel(writer, sheet_name='الحسابات', index=False)
            
            expenses_data = {
                'التاريخ': [datetime.now().strftime('%Y-%m-%d')],
                'النوع': ['دخل'],
                'المبلغ': [2000],
                'الحساب': ['💳 البنك الأهلي'],
                'التصنيف': ['💰 راتب']
            }
            pd.DataFrame(expenses_data).to_excel(writer, sheet_name='المعاملات', index=False)
            
            transfers_data = {
                'التاريخ': [datetime.now().strftime('%Y-%m-%d')],
                'من حساب': ['💳 البنك الأهلي'],
                'إلى حساب': ['💵 النقدي'],
                'المبلغ': [1000]
            }
            pd.DataFrame(transfers_data).to_excel(writer, sheet_name='التحويلات', index=False)

def load_data():
    accounts = pd.read_excel(EXCEL_FILE, sheet_name='الحسابات')
    transactions = pd.read_excel(EXCEL_FILE, sheet_name='المعاملات')
    transfers = pd.read_excel(EXCEL_FILE, sheet_name='التحويلات')
    return accounts, transactions, transfers

def save_data(accounts, transactions, transfers):
    with pd.ExcelWriter(EXCEL_FILE) as writer:
        accounts.to_excel(writer, sheet_name='الحسابات', index=False)
        transactions.to_excel(writer, sheet_name='المعاملات', index=False)
        transfers.to_excel(writer, sheet_name='التحويلات', index=False)

# أوامر البوت
def start(update: Update, context: CallbackContext):
    keyboard = [
        ['➕ إضافة مصروف', '💸 إضافة دخل'], 
        ['🔄 تحويل بين الحسابات', '📊 عرض الحسابات'], 
        ['📈 عرض المصروفات', '🏦 إضافة حساب جديد']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    update.message.reply_text(
        '👋 مرحباً! أنا بوت إدارة الحسابات الشخصية. \n\n'
        '📌 يمكنني مساعدتك في:\n'
        '• تسجيل المصروفات والدخل 💰\n'
        '• تحويل الأموال بين الحسابات 🔄\n'
        '• متابعة أرصدة حساباتك 📊\n'
        '• إنشاء تقارير مالية 📈\n\n'
        'اختر من الخيارات في لوحة المفاتيح: 👇', 
        reply_markup=reply_markup
    )

def show_accounts(update: Update, context: CallbackContext):
    accounts, _, _ = load_data()
    
    # ترتيب الحسابات من الأصغر إلى الأكبر
    accounts_sorted = accounts.sort_values(by='الرصيد', ascending=True)
    
    message = "💼 *حساباتك:*\n\n"
    total_balance = 0
    
    for _, account in accounts_sorted.iterrows():
        balance = account['الرصيد']
        original_account_name = account['اسم الحساب']
        
        # تنظيف اسم الحساب من الإيموجي
        cleaned_account_name = re.sub(r'[^\w\s]', '', original_account_name).strip()
        
        # إزالة الكسور العشرية إذا كانت صفر
        if balance == int(balance):
            formatted_balance = "{:,.0f}".format(balance)
        else:
            formatted_balance = "{:,.2f}".format(balance)
        
        formatted_balance = formatted_balance.replace(",", "٬")
        
        # تحديد الإيموجي المناسب
        emoji = "💵 "  # افتراضي
        
        if any(word in cleaned_account_name for word in ['أهلي', 'زراعات', 'بنك']):
            emoji = "🏛 "
        elif any(word in cleaned_account_name for word in ['ماستر', 'ائتمان', 'بطاقة']):
            emoji = "💳 "
        elif any(word in cleaned_account_name for word in ['صندوق', 'جيب', 'نقد']):
            emoji = "💵 "
        elif any(word in cleaned_account_name for word in ['مستحق', 'دين', 'قرض', 'مدين']):
            emoji = "📃 "
        elif any(word in cleaned_account_name for word in ['أبو', 'عم', 'خال', 'ابن']):
            emoji = "👤 "
        elif any(word in cleaned_account_name for word in ['رمضان', 'زكاة', 'صدقة']):
            emoji = "🕋 "
        elif any(word in cleaned_account_name for word in ['تذكرة', 'سفر', 'طيران']):
            emoji = "✈ "
        
        # إضافة السطر إلى الرسالة
        message += f"{emoji}*{cleaned_account_name}:* {formatted_balance} ريال\n"
        total_balance += balance
    
    # تنسيق الرصيد الإجمالي
    if total_balance == int(total_balance):
        formatted_total = "{:,.0f}".format(total_balance)
    else:
        formatted_total = "{:,.2f}".format(total_balance)
    formatted_total = formatted_total.replace(",", "٬")
    
    message += f"\n💰 *الإجمالي: {formatted_total} ريال*"
    
    update.message.reply_text(message, parse_mode='Markdown')

def show_expenses(update: Update, context: CallbackContext):
    _, transactions, _ = load_data()
    
    if transactions.empty:
        update.message.reply_text("📭 لا توجد معاملات مسجلة بعد.")
        return
    
    recent_transactions = transactions.tail(5)
    message = "📋 **آخر المعاملات:**\n\n"
    
    for _, transaction in recent_transactions.iterrows():
        emoji = "↗️" if transaction['النوع'] == 'مصروف' else "↙️"
        message += f"{emoji} {transaction['التاريخ']} - {transaction['التصنيف']}: {transaction['المبلغ']} ريال\n"
        message += f"   ({transaction['الحساب']})\n\n"
    
    update.message.reply_text(message, parse_mode='Markdown')

def add_expense(update: Update, context: CallbackContext):
    accounts, _, _ = load_data()
    
    # عرض الحسابات بدون الإيموجي للمستخدم
    accounts_list = get_accounts_without_emoji(accounts)
    
    update.message.reply_text(
        "💸 **إضافة مصروف جديد:**\n\n"
        "أدخل البيانات بالصيغة التالية:\n"
        "`التصنيف, المبلغ, اسم الحساب`\n\n"
        f"🏦 **الحسابات المتاحة:**\n{accounts_list}\n\n"
        "**أمثلة:**\n"
        "• `طعام, 50, النقدي`\n"
        "• `مواصلات, 30, البنك الأهلي`",
        parse_mode='Markdown'
    )
    return ADD_EXPENSE

def add_income(update: Update, context: CallbackContext):
    accounts, _, _ = load_data()
    
    # عرض الحسابات بدون الإيموجي للمستخدم
    accounts_list = get_accounts_without_emoji(accounts)
    
    update.message.reply_text(
        "💰 **إضافة دخل جديد:**\n\n"
        "أدخل البيانات بالصيغة التالية:\n"
        "`المصدر, المبلغ, اسم الحساب`\n\n"
        f"🏦 **الحسابات المتاحة:**\n{accounts_list}\n\n"
        "**أمثلة:**\n"
        "• `راتب, 5000, البنك الأهلي`\n"
        "• `عمل حر, 300, النقدي`",
        parse_mode='Markdown'
    )
    return ADD_INCOME

def transfer_money(update: Update, context: CallbackContext):
    accounts, _, _ = load_data()
    
    # عرض الحسابات بدون الإيموجي للمستخدم
    accounts_list = get_accounts_without_emoji(accounts)
    
    update.message.reply_text(
        "🔄 **تحويل بين الحسابات:**\n\n"
        "أدخل البيانات بالصيغة التالية:\n"
        "`من حساب, إلى حساب, المبلغ`\n\n"
        f"🏦 **الحسابات المتاحة:**\n{accounts_list}\n\n"
        "**مثال:**\n"
        "`البنك الأهلي, النقدي, 1000`",
        parse_mode='Markdown'
    )
    return TRANSFER

def handle_add_expense(update: Update, context: CallbackContext):
    try:
        data = update.message.text.split(',')
        if len(data) < 3:
            update.message.reply_text("❌ خطأ في الصيغة. يجب إدخال: التصنيف, المبلغ, الحساب")
            return ConversationHandler.END
            
        category = data[0].strip()
        amount = float(data[1].strip())
        account_input = data[2].strip()
        
        accounts, transactions, transfers = load_data()
        
        # البحث عن اسم الحساب باستخدام الدالة الجديدة
        account_name = get_account_name(account_input, accounts)
        if not account_name:
            update.message.reply_text("❌ الحساب غير موجود!")
            return ConversationHandler.END
        
        # تحديث رصيد الحساب
        account_index = accounts[accounts['اسم الحساب'] == account_name].index
        accounts.at[account_index[0], 'الرصيد'] -= amount
        
        # إضافة المعاملة
        new_transaction = {
            'التاريخ': datetime.now().strftime('%Y-%m-%d'),
            'النوع': 'مصروف',
            'المبلغ': amount,
            'الحساب': account_name,
            'التصنيف': category
        }
        transactions = pd.concat([transactions, pd.DataFrame([new_transaction])], ignore_index=True)
        
        save_data(accounts, transactions, transfers)
        update.message.reply_text(f"✅ تم تسجيل مصروف {amount} ريال من {account_name} للتصنيف {category}")
    except ValueError:
        update.message.reply_text("❌ المبلغ يجب أن يكون رقماً!")
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
    
    return ConversationHandler.END

def handle_add_income(update: Update, context: CallbackContext):
    try:
        data = update.message.text.split(',')
        if len(data) < 3:
            update.message.reply_text("❌ خطأ في الصيغة. يجب إدخال: المصدر, المبلغ, الحساب")
            return ConversationHandler.END
            
        source = data[0].strip()
        amount = float(data[1].strip())
        account_input = data[2].strip()
        
        accounts, transactions, transfers = load_data()
        
        # البحث عن اسم الحساب باستخدام الدالة الجديدة
        account_name = get_account_name(account_input, accounts)
        if not account_name:
            update.message.reply_text("❌ الحساب غير موجود!")
            return ConversationHandler.END
        
        # تحديث رصيد الحساب
        account_index = accounts[accounts['اسم الحساب'] == account_name].index
        accounts.at[account_index[0], 'الرصيد'] += amount
        
        # إضافة المعاملة
        new_transaction = {
            'التاريخ': datetime.now().strftime('%Y-%m-%d'),
            'النوع': 'دخل',
            'المبلغ': amount,
            'الحساب': account_name,
            'التصنيف': source
        }
        transactions = pd.concat([transactions, pd.DataFrame([new_transaction])], ignore_index=True)
        
        save_data(accounts, transactions, transfers)
        update.message.reply_text(f"✅ تم تسجيل دخل {amount} ريال إلى {account_name} من {source}")
    except ValueError:
        update.message.reply_text("❌ المبلغ يجب أن يكون رقماً!")
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
    
    return ConversationHandler.END

def handle_transfer(update: Update, context: CallbackContext):
    try:
        data = update.message.text.split(',')
        if len(data) < 3:
            update.message.reply_text("❌ خطأ في الصيغة. يجب إدخال: من حساب, إلى حساب, المبلغ")
            return ConversationHandler.END
            
        from_acc_input = data[0].strip()
        to_acc_input = data[1].strip()
        amount = float(data[2].strip())
        
        accounts, transactions, transfers = load_data()
        
        # البحث عن أسماء الحسابات باستخدام الدالة الجديدة
        from_acc = get_account_name(from_acc_input, accounts)
        to_acc = get_account_name(to_acc_input, accounts)
        
        if not from_acc or not to_acc:
            update.message.reply_text("❌ أحد الحسابات غير موجود!")
            return ConversationHandler.END
        
        # التحقق من الرصيد الكافي
        from_index = accounts[accounts['اسم الحساب'] == from_acc].index
        if accounts.at[from_index[0], 'الرصيد'] < amount:
            update.message.reply_text("❌ الرصيد غير كافي!")
            return ConversationHandler.END
        
        # إجراء التحويل
        accounts.at[from_index[0], 'الرصيد'] -= amount
        to_index = accounts[accounts['اسم الحساب'] == to_acc].index
        accounts.at[to_index[0], 'الرصيد'] += amount
        
        # تسجيل التحويل
        new_transfer = {
            'التاريخ': datetime.now().strftime('%Y-%m-%d'),
            'من حساب': from_acc,
            'إلى حساب': to_acc,
            'المبلغ': amount
        }
        transfers = pd.concat([transfers, pd.DataFrame([new_transfer])], ignore_index=True)
        
        save_data(accounts, transactions, transfers)
        update.message.reply_text(f"✅ تم تحويل {amount} ريال من {from_acc} إلى {to_acc}")
    except ValueError:
        update.message.reply_text("❌ المبلغ يجب أن يكون رقماً!")
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
    
    return ConversationHandler.END

def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("❌ تم الإلغاء.")
    return ConversationHandler.END

def handle_message(update: Update, context: CallbackContext):
    text = update.message.text
    if text == '📊 عرض الحسابات':
        show_accounts(update, context)
    elif text == '📈 عرض المصروفات':
        show_expenses(update, context)
    else:
        update.message.reply_text("👋 استخدم الأزرار في لوحة المفاتيح للتفاعل مع البوت")
# دالة للتحقق مما إذا كان الحساب يسمح بالرصيد السالب
def allows_negative_balance(account_type, account_name):
    """
    تحديد ما إذا كان الحساب يسمح بالرصيد السالب
    """
    # الحسابات التي تسمح بالرصيد السالب (ديون، بطاقات ائتمان، قروض)
    negative_allowed_types = ['دين', 'بطاقة ائتمان', 'قرض', 'ديون']
    negative_allowed_keywords = ['مستحق', 'دين', 'قرض', 'ائتمان', 'مدين', 'ديون']
    
    # التحقق من نوع الحساب
    if account_type in negative_allowed_types:
        return True
    
    # التحقق من كلمات مفتاحية في اسم الحساب
    account_name_lower = account_name.lower()
    for keyword in negative_allowed_keywords:
        if keyword in account_name_lower:
            return True
    
    return False

# في دالة handle_transfer، غير جزء التحقق من الرصيد:
def handle_transfer(update: Update, context: CallbackContext):
    try:
        data = update.message.text.split(',')
        if len(data) < 3:
            update.message.reply_text("❌ خطأ في الصيغة. يجب إدخال: من حساب, إلى حساب, المبلغ")
            return ConversationHandler.END
            
        from_acc_input = data[0].strip()
        to_acc_input = data[1].strip()
        amount = float(data[2].strip())
        
        accounts, transactions, transfers = load_data()
        
        # البحث عن أسماء الحسابات
        from_acc = get_account_name(from_acc_input, accounts)
        to_acc = get_account_name(to_acc_input, accounts)
        
        if not from_acc or not to_acc:
            update.message.reply_text("❌ أحد الحسابات غير موجود!")
            return ConversationHandler.END
        
        # الحصول على معلومات الحساب المصدر
        from_account_info = accounts[accounts['اسم الحساب'] == from_acc].iloc[0]
        from_balance = from_account_info['الرصيد']
        from_type = from_account_info['النوع']
        
        # التحقق من الرصيد (مع السماح بالرصيد السالب للحسابات المسموحة فقط)
        if from_balance < amount and not allows_negative_balance(from_type, from_acc):
            update.message.reply_text(
                f"❌ الرصيد غير كافي في {from_acc}!\n"
                f"💵 الرصيد الحالي: {from_balance} ريال\n"
                f"💸 المبلغ المطلوب: {amount} ريال\n\n"
                f"📋 ملاحظة: هذا الحساب لا يسمح بالرصيد السالب."
            )
            return ConversationHandler.END
        
        # إذا كان الرصيد غير كافي ولكن الحساب يسمح بالسالب
        if from_balance < amount:
            update.message.reply_text(
                f"⚠️ تحذير: الرصيد غير كافي، ولكن سيصبح الرصيد سالباً!\n"
                f"💵 الرصيد الحالي: {from_balance} ريال\n"
                f"💸 المبلغ المطلوب: {amount} ريال\n"
                f"🔻 الرصيد الجديد: {from_balance - amount} ريال\n\n"
                f"✅ للمتابعة، أرسل 'نعم' أو ❌ للإلغاء أرسل 'لا'"
            )
            # حفظ البيانات مؤقتاً للموافقة
            context.user_data['pending_transfer'] = {
                'from_acc': from_acc,
                'to_acc': to_acc,
                'amount': amount,
                'accounts': accounts,
                'transactions': transactions,
                'transfers': transfers
            }
            return TRANSFER_CONFIRM  # حالة جديدة للموافقة
        
        # إذا كان الرصيد كافي، تنفيذ التحويل مباشرة
        return execute_transfer(update, from_acc, to_acc, amount, accounts, transactions, transfers)
        
    except ValueError:
        update.message.reply_text("❌ المبلغ يجب أن يكون رقماً!")
        return ConversationHandler.END
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
        return ConversationHandler.END

# حالة جديدة للموافقة على التحويل مع رصيد سالب
TRANSFER_CONFIRM = 5

# دالة تنفيذ التحويل
def execute_transfer(update, from_acc, to_acc, amount, accounts, transactions, transfers):
    # تحديث الرصيد
    from_index = accounts[accounts['اسم الحساب'] == from_acc].index
    to_index = accounts[accounts['اسم الحساب'] == to_acc].index
    
    accounts.at[from_index[0], 'الرصيد'] -= amount
    accounts.at[to_index[0], 'الرصيد'] += amount
    
    # تسجيل التحويل
    new_transfer = {
        'التاريخ': datetime.now().strftime('%Y-%m-%d'),
        'من حساب': from_acc,
        'إلى حساب': to_acc,
        'المبلغ': amount
    }
    transfers = pd.concat([transfers, pd.DataFrame([new_transfer])], ignore_index=True)
    
    save_data(accounts, transactions, transfers)
    
    # الحصول على الرصيد الجديد
    new_balance = accounts.at[from_index[0], 'الرصيد']
    
    update.message.reply_text(
        f"✅ تم تحويل {amount} ريال من {from_acc} إلى {to_acc}\n"
        f"💵 الرصيد الجديد في {from_acc}: {new_balance} ريال"
    )
    return ConversationHandler.END

# معالجة الموافقة على التحويل
def handle_transfer_confirm(update: Update, context: CallbackContext):
    user_response = update.message.text.strip().lower()
    
    if user_response in ['نعم', 'yes', 'y', 'ok', 'موافق']:
        # تنفيذ التحويل
        transfer_data = context.user_data['pending_transfer']
        return execute_transfer(
            update,
            transfer_data['from_acc'],
            transfer_data['to_acc'],
            transfer_data['amount'],
            transfer_data['accounts'],
            transfer_data['transactions'],
            transfer_data['transfers']
        )
    else:
        update.message.reply_text("❌ تم إلغاء التحويل.")
        return ConversationHandler.END

def main():
    init_excel_file()
    
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dispatcher = updater.dispatcher
    
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(Filters.regex('^➕ إضافة مصروف$'), add_expense),
            MessageHandler(Filters.regex('^💸 إضافة دخل$'), add_income),
            MessageHandler(Filters.regex('^🔄 تحويل بين الحسابات$'), transfer_money)
        ],
        states={
            ADD_EXPENSE: [MessageHandler(Filters.text & ~Filters.command, handle_add_expense)],
            ADD_INCOME: [MessageHandler(Filters.text & ~Filters.command, handle_add_income)],
            TRANSFER: [MessageHandler(Filters.text & ~Filters.command, handle_transfer)],
            TRANSFER_CONFIRM: [MessageHandler(Filters.text & ~Filters.command, handle_transfer_confirm)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    
    print("🤖 البوت يعمل...")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()