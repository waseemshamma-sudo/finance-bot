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

# قائمة المستخدمين المسموح لهم (استبدل بمعرفاتك الحقيقية)
ALLOWED_USER_IDS = [1919573036, 987654321]  # أضف معرفات المستخدمين المسموح لهم

ACCOUNT_MAPPING = {
    # البطاقات الائتمانية
    '6600': '💳 ماستر',
    '3373': '💳 ماستر', 
    '5805': '💳 ماستر',
    
    # الحسابات البنكية  
    '0103': '🏛 أهلي 121',
    '0105': '🏛 أهلي 136',
    '8825': '🏛 إس تي سي',
    '1127': '🏛 إس تي سي',  # تم التصحيح
    '9281': '🏛 راجحي',
    '2842': '🏛 راجحي',
}

# دالة للتحقق من الصلاحيات
def restricted(func):
    def wrapper(update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        if user_id not in ALLOWED_USER_IDS:
            update.message.reply_text("⛔ ليس لديك صلاحية استخدام هذا البوت")
            return ConversationHandler.END
        return func(update, context)
    return wrapper

# حالات المحادثة
ADD_EXPENSE, ADD_INCOME, TRANSFER, NEW_ACCOUNT, CATEGORY, TRANSFER_CONFIRM, PROCESS_BANK_MSG, CONFIRM_TRANSACTION = range(8)
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
            
            # إضافة عمود الوصف للمعاملات
            expenses_data = {
                'التاريخ': [datetime.now().strftime('%Y-%m-%d')],
                'النوع': ['دخل'],
                'المبلغ': [2000],
                'الحساب': ['💳 البنك الأهلي'],
                'التصنيف': ['💰 راتب'],
                'الوصف': ['الراتب الشهري']  # العمود الجديد
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
    
    # إذا كان عمود الوصف غير موجود، إضافته
    if 'الوصف' not in transactions.columns:
        transactions['الوصف'] = ''
    
    transfers = pd.read_excel(EXCEL_FILE, sheet_name='التحويلات')
    return accounts, transactions, transfers

def save_data(accounts, transactions, transfers):
    with pd.ExcelWriter(EXCEL_FILE) as writer:
        accounts.to_excel(writer, sheet_name='الحسابات', index=False)
        transactions.to_excel(writer, sheet_name='المعاملات', index=False)
        transfers.to_excel(writer, sheet_name='التحويلات', index=False)

# التصنيفات التلقائية للمعاملات
AUTO_CATEGORIES = {
    'al faisal': '🍔 طعام',
    'bajh trad': '🛒 تسوق',
    'landmark': '👕 ملابس',
    'price reducer': '🛒 سوبرماركت',
    'barakah': '🍔 طعام',
    'consumer river': '🛒 تسوق',
    'restaurant': '🍔 طعام',
    'coffee': '☕ مقهى',
    'supermarket': '🛒 سوبرماركت',
    'grocery': '🛒 سوبرماركت',
    'clothing': '👕 ملابس',
    'electronics': '📱 إلكترونيات',
    'fuel': '⛽ بنزين',
    'transport': '🚗 مواصلات',
    'alsalah': '🛒 سوبرماركت',
    'lounge': '🍔 طعام',
    'economy': '🍔 طعام',
}

def parse_date_from_message(date_str):
    """تحويل التاريخ من الصيغ المختلفة إلى صيغة قياسية YYYY-MM-DD"""
    try:
        if not date_str:
            return None
            
        # إزالة أي مسافات زائدة
        date_str = date_str.strip()
        
        # تحديد الفاصل المستخدم (/ أو -)
        if '/' in date_str:
            parts = date_str.split('/')
        elif '-' in date_str:
            parts = date_str.split('-')
        else:
            return None
        
        if len(parts) != 3:
            return None
        
        # تنظيف الأجزاء من أي مسافات
        parts = [part.strip() for part in parts]
        
        # تحديد تنسيق التاريخ (افترض DD/MM/YY)
        # إذا كان الجزء الأول أكبر من 31 فهو likely السنة
        if len(parts[0]) == 4 or int(parts[0]) > 31:
            # التنسيق: YYYY/MM/DD أو YY/MM/DD
            year, month, day = parts
        elif int(parts[2]) > 31:
            # التنسيق: DD/MM/YYYY أو DD/MM/YY
            day, month, year = parts
        else:
            # افترض التنسيق: DD/MM/YY
            day, month, year = parts
        
        # تحويل السنة إلى 4 أرقام إذا كانت مكونة من رقمين
        if len(year) == 2:
            # تحديد القرن المناسب (افترض القرن 21 للسنوات 00-99)
            year = '20' + year
        
        # تحويل اليوم والشهر إلى صيغة مكونة من رقمين
        day = day.zfill(2)
        month = month.zfill(2)
        
        # التحقق من صحة التاريخ
        datetime.strptime(f"{year}-{month}-{day}", "%Y-%m-%d")
        
        return f"{year}-{month}-{day}"
        
    except Exception as e:
        print(f"Error parsing date {date_str}: {e}")
        return None


def parse_date_from_message(date_str):
    """محاولة تحويل التاريخ إلى yyyy-mm-dd"""
    date_formats = [
        "%d/%m/%Y",
        "%d/%m/%y",
        "%d-%m-%Y",
        "%d-%m-%y",
        "%d-%m-%y %H:%M",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M"
    ]
    for fmt in date_formats:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def parse_bank_message(message):
    """تحليل رسالة البنك واستخراج البيانات"""
    try:
        message_lower = message.lower()
        
        # تحديد نوع المعاملة
        transaction_type = None
        if re.search(r'pos purchase|شراء|عملية شراء|بطاقة|مدى|مدى باي|online purchase|شراء اون لاين', message_lower):
            transaction_type = 'مصروف'
        elif re.search(r'transfer|تحويل|حوالة|مدفوعات|دفع|خدمات', message_lower):
            transaction_type = 'مصروف'
        elif re.search(r'deposit|إيداع|رواتب|payroll', message_lower):
            transaction_type = 'دخل'
        
        # استخراج المبلغ
        amount = None
        amount_match = re.search(r'(?:amount|مبلغ)[:\s]*sar?\s*([\d,]+(?:\.\d{1,2})?)', message_lower, re.IGNORECASE)
        if not amount_match:
            amount_match = re.search(r'([\d,]+(?:\.\d{1,2})?)\s*(?:sar|ر\.س)', message_lower)
        if amount_match:
            try:
                amount = float(amount_match.group(1).replace(',', ''))
            except:
                pass
        
        # استخراج الجهة (merchant)
        merchant = None
        merchant_match = re.search(r'(?:at|عند|من|لدى)[:\s]*([^\n]+)', message, re.IGNORECASE)
        if merchant_match:
            merchant = merchant_match.group(1).strip()
        
        # استخراج التاريخ
        date_str = None
        date_match = re.search(r'(\d{1,2}[-/]\d{1,2}[-/]\d{2,4}(?: \d{1,2}:\d{2})?)', message)
        if date_match:
            date_str = date_match.group(1).strip()
        
        if date_str:
            parsed_date = parse_date_from_message(date_str)
            if parsed_date:
                date_str = parsed_date
            else:
                date_str = datetime.now().strftime('%Y-%m-%d')
        else:
            date_str = datetime.now().strftime('%Y-%m-%d')
        
        # التعرف على الحساب من خلال الأرقام
        account = None
        for acc_number, acc_name in ACCOUNT_MAPPING.items():
            if acc_number in message:
                account = acc_name
                break
        
        if not account:
            acc_match = re.search(r'\d{4}', message)  # آخر 4 أرقام البطاقة
            if acc_match:
                account = ACCOUNT_MAPPING.get(acc_match.group(), f"💳 بطاقة {acc_match.group()}")
            elif re.search(r'credit card|بطاقة|visa|mastercard', message_lower):
                account = '💳 ماستر'
            elif re.search(r'account|حساب|بنك|bank', message_lower):
                account = '🏦 أهلي 136'
        
        # التصنيف التلقائي
        category = 'أخرى'
        if merchant:
            for keyword, cat in AUTO_CATEGORIES.items():
                if keyword.lower() in merchant.lower():
                    category = cat
                    break
        
        if transaction_type and amount:
            return {
                'type': transaction_type,
                'amount': amount,
                'merchant': merchant,
                'date': date_str,
                'account': account,
                'category': category
            }
        
        # لو ما انمسكت نرجع الرسالة نفسها (debug mode)
        return {"raw_message": message}
        
    except Exception as e:
        logging.error("Error parsing bank message", exc_info=True)
        return {"raw_message": message}

# تنسيق البيانات للموافقة
def format_transaction_for_approval(transaction_data):
    """تنسيق بيانات المعاملة للموافقة عليها"""
    message = "✅ <b>تم التعرف على المعاملة:</b>\n\n"
    message += f"📋 <b>النوع:</b> {transaction_data['type']}\n"
    message += f"💰 <b>المبلغ:</b> {transaction_data['amount']:,.2f} ريال\n"
    
    if transaction_data.get('merchant'):
        message += f"🏪 <b>الجهة/الوصف:</b> {transaction_data['merchant']}\n"
    
    if transaction_data.get('category'):
        message += f"🏷️ <b>التصنيف:</b> {transaction_data['category']}\n"
    
    if transaction_data.get('account'):
        message += f"🏦 <b>الحساب:</b> {transaction_data['account']}\n"
    
    if transaction_data.get('date'):
        message += f"📅 <b>التاريخ:</b> {transaction_data['date']}\n"
    
    # عرض جزء من الرسالة الأصلية للمساعدة في التحقق
    if 'original_message' in transaction_data:
        preview = transaction_data['original_message'][:100] + "..." if len(transaction_data['original_message']) > 100 else transaction_data['original_message']
        message += f"\n📄 <b>جزء من الرسالة:</b>\n<code>{preview}</code>\n"
    
    message += "\n📝 <b>للموافقة أرسل:</b> نعم\n❌ <b>للإلغاء أرسل:</b> لا"
    
    return message

# أوامر البوت

@restricted
def start(update: Update, context: CallbackContext):
    keyboard = [
        ['➕ إضافة مصروف', '💸 إضافة دخل'], 
        ['🔄 تحويل بين الحسابات', '📊 عرض الحسابات'], 
        ['📈 عرض المصروفات', '🏦 إضافة حساب جديد'],
        ['📋 كشف حساب', '🏦 معالجة رسالة بنك']  # الزر الجديد
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    update.message.reply_text(
        '👋 مرحباً! أنا بوت إدارة الحسابات الشخصية. \n\n'
        '📌 يمكنني مساعدتك في:\n'
        '• تسجيل المصروفات والدخل 💰\n'
        '• تحويل الأموال بين الحسابات 🔄\n'
        '• متابعة أرصدة حساباتك 📊\n'
        '• إنشاء تقارير مالية 📈\n'
        '• معالجة رسائل البنك تلقائياً 🏦\n\n'
        'اختر من الخيارات في لوحة المفاتيح: 👇', 
        reply_markup=reply_markup
    )

@restricted
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
        
        if any(word in cleaned_account_name for word in ['أهلي', 'تي', 'راج', 'زراعات', 'بنك']):
            emoji = "🏛 "
        elif any(word in cleaned_account_name for word in ['ماستر', 'ائتمان', 'بطاقة']):
            emoji = "💳 "
        elif any(word in cleaned_account_name for word in ['صندوق', 'جيب', 'نقد']):
            emoji = "💵 "
        elif any(word in cleaned_account_name for word in ['مستحق', 'دين', 'قرض', 'مدين']):
            emoji = "📃 "
        elif any(word in cleaned_account_name for word in ['بو', 'عم', 'جاري', 'خال', 'ابن']):
            emoji = "👤 "
        elif any(word in cleaned_account_name for word in ['رمضان', 'زكاة', 'صدقة']):
            emoji = "🕋 "
        elif any(word in cleaned_account_name for word in ['تذكرة', 'سفر', 'طيران']):
            emoji = "✈ "
        
        # إضافة السطر إلى الرسالة
        message += f"{emoji}*{cleaned_account_name}: {formatted_balance} ريال*\n"
        total_balance += balance
    
    # تنسيق الرصيد الإجمالي
    if total_balance == int(total_balance):
        formatted_total = "{:,.0f}".format(total_balance)
    else:
        formatted_total = "{:,.2f}".format(total_balance)
    formatted_total = formatted_total.replace(",", "٬")
    
    message += f"\n💰 *الإجمالي: {formatted_total} ريال*"
    
    update.message.reply_text(message, parse_mode='Markdown')

@restricted
def show_expenses(update: Update, context: CallbackContext):
    _, transactions, _ = load_data()
    
    if transactions.empty:
        update.message.reply_text("📭 لا توجد معاملات مسجلة بعد.")
        return
    
    recent_transactions = transactions.tail(10)
    message = "📋 **آخر المعاملات:**\n\n"
    
    for _, transaction in recent_transactions.iterrows():
        emoji = "↗️" if transaction['النوع'] == 'مصروف' else "↙️"
        message += f"{emoji} {transaction['التاريخ']} - {transaction['التصنيف']}: {transaction['المبلغ']} ريال\n"
        message += f"   ({transaction['الحساب']})\n\n"
    
    update.message.reply_text(message, parse_mode='Markdown')

@restricted
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
        "• `طعام, 50, راجح`\n"
        "• `مواصلات, 30, أهلي`",
        parse_mode='Markdown'
    )
    return ADD_EXPENSE

@restricted
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
        "• `راتب, 5000, أهلي`\n"
        "• `عمل حر, 300, زراع`",
        parse_mode='Markdown'
    )
    return ADD_INCOME

@restricted
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
        "`ماستر, 136, 1000`",
        parse_mode='Markdown'
    )
    return TRANSFER

@restricted
def process_bank_message(update: Update, context: CallbackContext):
    update.message.reply_text(
        "🏦 **معالجة رسالة بنك تلقائية:**\n\n"
        "أرسل لي رسالة البنك وسأحاول معالجتها تلقائياً.\n\n"
        "📋 **المدعوم حالياً:**\n"
        "• مشتريات POS\n• تحويلات\n• إيداعات رواتب\n• مشتريات онлайн\n"
        "• رسائل البنك الأهلي والراجحي\n\n"
        "أرسل الرسالة الآن:",
        parse_mode='Markdown'
    )
    return PROCESS_BANK_MSG

@restricted
def handle_bank_message(update: Update, context: CallbackContext):
    try:
        message = update.message.text
        transaction_data = parse_bank_message(message)
        
        if transaction_data:
            # حفظ البيانات مؤقتاً للموافقة بما في ذلك الرسالة الأصلية
            transaction_data['original_message'] = message  # حفظ الرسالة الأصلية
            context.user_data['pending_transaction'] = transaction_data
            
            # عرض البيانات للموافقة
            response = format_transaction_for_approval(transaction_data)
            update.message.reply_text(response, parse_mode='HTML')
            
            return CONFIRM_TRANSACTION
            
        else:
            update.message.reply_text(
                "❌ لم أستطع فهم رسالة البنك.\n"
                "يمكنك إدخال المعاملة يدوياً باستخدام الخيارات الأخرى.\n\n"
                "💡 <b>نصائح للمساعدة:</b>\n"
                "• تأكد من وجود كلمات مثل 'شراء'، 'تحويل'، 'مبلغ'\n"
                "• تأكد من وجود رقم الحساب أو البطاقة\n"
                "• تأكد من وجود تاريخ المعاملة\n",
                parse_mode='HTML'
            )
            return ConversationHandler.END
            
    except Exception as e:
        update.message.reply_text(f"❌ حدث خطأ: {str(e)}")
        return ConversationHandler.END
@restricted
def handle_transaction_confirmation(update: Update, context: CallbackContext):
    try:
        user_response = update.message.text.strip().lower()
        
        if user_response in ['نعم', 'yes', 'y', 'ok', 'موافق']:
            transaction_data = context.user_data.get('pending_transaction')
            
            if transaction_data:
                accounts, transactions, transfers = load_data()
                
                # تحديد الحساب إذا لم يتم التعرف عليه تلقائياً
                if not transaction_data['account']:
                    # افتراضي بطاقة الائتمان للمصروفات، البنك للدخل
                    transaction_data['account'] = '💳 بطاقة الائتمان' if transaction_data['type'] == 'مصروف' else '💳 البنك الأهلي'
                
                # البحث عن اسم الحساب
                account_name = get_account_name(transaction_data['account'], accounts)
                if not account_name:
                    update.message.reply_text("❌ الحساب غير موجود!")
                    return ConversationHandler.END
                
                # تحديث رصيد الحساب
                account_index = accounts[accounts['اسم الحساب'] == account_name].index
                
                if transaction_data['type'] == 'مصروف':
                    accounts.at[account_index[0], 'الرصيد'] -= transaction_data['amount']
                else:  # دخل
                    accounts.at[account_index[0], 'الرصيد'] += transaction_data['amount']
                
                new_balance = accounts.at[account_index[0], 'الرصيد']
                
                # استخدام التاريخ من رسالة البنك أو التاريخ الحالي إذا لم يكن موجوداً
                transaction_date = transaction_data.get('date')
                if not transaction_date:
                    transaction_date = datetime.now().strftime('%Y-%m-%d')
                
                # إضافة المعاملة مع الوصف
                new_transaction = {
                    'التاريخ': transaction_date,  # استخدام التاريخ المستخلص
                    'النوع': transaction_data['type'],
                    'المبلغ': transaction_data['amount'],
                    'الحساب': account_name,
                    'التصنيف': transaction_data['category'],
                    'الوصف': transaction_data.get('merchant', '')  # إضافة الوصف
                }
                transactions = pd.concat([transactions, pd.DataFrame([new_transaction])], ignore_index=True)
                
                save_data(accounts, transactions, transfers)
                
                # حساب الموازنة
                budget = calculate_budget()
                
                # تنظيف اسم الحساب من الإيموجي للعرض
                cleaned_account_name = re.sub(r'[^\w\s]', '', account_name).strip()
                
                # إرسال الرسالة بتنسيق HTML مع النص الغامق
                message = (
                    f"✅ تم تسجيل {transaction_data['type']} {transaction_data['amount']} ريال "
                    f"في {account_name} للتصنيف {transaction_data['category']}\n"
                )
                
                if transaction_data.get('merchant'):
                    message += f"🏪 الوصف: {transaction_data['merchant']}\n"
                
                message += (
                    f"<b>📅 التاريخ: {transaction_date}</b>\n"
                    f"<b>💵 الرصيد الجديد في:</b>\n"
                    f"<b>▪ {cleaned_account_name}: {new_balance:,.1f} ريال</b>\n"
                    f"<b>▪ موازنة : {budget:,.0f} ريال</b>"
                )
                
                update.message.reply_text(message, parse_mode='HTML')
            else:
                update.message.reply_text("❌ لا توجد معاملة معلقة!")
        else:
            update.message.reply_text("❌ تم إلغاء المعاملة.")
        
        return ConversationHandler.END
        
    except Exception as e:
        update.message.reply_text(f"❌ حدث خطأ: {str(e)}")
        return ConversationHandler.END


@restricted
def handle_add_expense(update: Update, context: CallbackContext):
    try:
        data = update.message.text.split(',')
        if len(data) < 3:
            update.message.reply_text("❌ خطأ في الصيغة. يجب إدخال: التصنيف, المبلغ, الحساب")
            return ConversationHandler.END
            
        category = data[0].strip()
        amount = float(data[1].strip())
        account_input = data[2].strip()
        
        # الحصول على الوصف إذا كان موجوداً
        description = data[3].strip() if len(data) > 3 else ''
        
        accounts, transactions, transfers = load_data()
        
        # البحث عن اسم الحساب باستخدام الدالة الجديدة
        account_name = get_account_name(account_input, accounts)
        if not account_name:
            update.message.reply_text("❌ الحساب غير موجود!")
            return ConversationHandler.END
        
        # تحديث رصيد الحساب
        account_index = accounts[accounts['اسم الحساب'] == account_name].index
        accounts.at[account_index[0], 'الرصيد'] -= amount
        new_balance = accounts.at[account_index[0], 'الرصيد']  # الحصول على الرصيد الجديد
        
        # إضافة المعاملة مع الوصف
        new_transaction = {
            'التاريخ': datetime.now().strftime('%Y-%m-%d'),
            'النوع': 'مصروف',
            'المبلغ': amount,
            'الحساب': account_name,
            'التصنيف': category,
            'الوصف': description  # إضافة الوصف
        }
        transactions = pd.concat([transactions, pd.DataFrame([new_transaction])], ignore_index=True)
        
        save_data(accounts, transactions, transfers)
        
        # حساب الموازنة
        budget = calculate_budget()
        
        # تنظيف اسم الحساب من الإيموجي للعرض
        cleaned_account_name = re.sub(r'[^\w\s]', '', account_name).strip()
        
        # إرسال الرسالة بتنسيق HTML مع النص الغامق
        message = (
            f"<b>✅ تم تسجيل مصروف {amount} ريال  للتصنيف {category}</b>\n"
            f"<b>  من : {account_name}  </b>\n"

        )
        
        if description:
            message += f"🏪 الوصف: {description}\n"
            
        message += (
            f"<b>💵 الرصيد الجديد في:</b>\n"
            f"<b>▪ {cleaned_account_name}: {new_balance:,.1f} ريال</b>\n"
            f"<b>▪ موازنة : {budget:,.0f} ريال</b>"
        )
        update.message.reply_text(message, parse_mode='HTML')
    except ValueError:
        update.message.reply_text("❌ المبلغ يجب أن يكون رقماً!")
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
    
    return ConversationHandler.END
@restricted
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
        new_balance = accounts.at[account_index[0], 'الرصيد']  # الحصول على الرصيد الجديد
        
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
        
        # حساب الموازنة
        budget = calculate_budget()
        
        # تنظيف اسم الحساب من الإيموجي للعرض
        cleaned_account_name = re.sub(r'[^\w\s]', '', account_name).strip()
        
        # إرسال الرسالة بتنسيق HTML مع النص الغامق
        message = (
            f"<b>✅ تم تسجيل دخل من : {source} {amount:,.1f} ريال</b>\n"
            f"<b> إلى : {account_name}</b>\n"
            f"<b>💵 الرصيد الجديد :</b>\n"
            f"<b>▪ {cleaned_account_name}: {new_balance:,.1f} ريال</b>\n"
            f"<b>▪ موازنة : {budget:,.0f} ريال</b>"
        )
        update.message.reply_text(message, parse_mode='HTML')
    except ValueError:
        update.message.reply_text("❌ المبلغ يجب أن يكون رقماً!")
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
    
    return ConversationHandler.END

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

@restricted
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

def escape_markdown_v2(text):
    """تهريب الأحرف الخاصة في MarkdownV2"""
    escape_chars = r'\_*[]()~`>#+-=|{}.!'
    return re.sub(f'([{re.escape(escape_chars)}])', r'\\\1', str(text))




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
    
    # الحصول على الرصيد الجديد لكلا الحسابين
    from_balance = accounts.at[from_index[0], 'الرصيد']
    to_balance = accounts.at[to_index[0], 'الرصيد']
    
    # حساب الموازنة
    budget = calculate_budget()
    
    # تنظيف أسماء الحسابات من الإيموجي للعرض
    from_cleaned = re.sub(r'[^\w\s]', '', from_acc).strip()
    to_cleaned = re.sub(r'[^\w\s]', '', to_acc).strip()
    
    # إرسال الرسالة بتنسيق HTML مع النص الغامق
    message = (
        f"<b>✅ تم تحويل {amount} ريال من {from_acc} إلى {to_acc}</b>\n"
        f"<b>💵 الرصيد الجديد :</b>\n"
        f"<b>▪ {from_cleaned}: {from_balance:,.1f} ريال</b>\n"
        f"<b>▪ {to_cleaned}: {to_balance:,.1f} ريال</b>\n"
        f"<b>▪ موازنة : {budget:,.0f} ريال</b>"
    )
    
    # إرسال الرسالة مع parse_mode='HTML'
    update.message.reply_text(message, parse_mode='HTML')
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

@restricted
def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("❌ تم الإلغاء.")
    return ConversationHandler.END

@restricted
def handle_message(update: Update, context: CallbackContext):
    text = update.message.text
    if text == '📊 عرض الحسابات':
        show_accounts(update, context)
    elif text == '📈 عرض المصروفات':
        show_expenses(update, context)
    elif text == '🏦 إضافة حساب جديد':
        add_new_account(update, context)
    elif text == '📋 كشف حساب':
        account_statement(update, context)
    elif text == '🏦 معالجة رسالة بنك':
        process_bank_message(update, context)
    else:
        update.message.reply_text("👋 استخدم الأزرار في لوحة المفاتيح للتفاعل مع البوت")

@restricted
def add_new_account(update: Update, context: CallbackContext):
    update.message.reply_text(
        "🏦 **إضافة حساب جديد:**\n\n"
        "أدخل بيانات الحساب بالصيغة التالية:\n"
        "`اسم الحساب, النوع, الرصيد الأولي`\n\n"
        "📋 **أنواع الحسابات المتاحة:**\n"
        "• `بنك` - للحسابات البنكية 🏛\n"
        "• `بطاقة ائتمان` - للبطاقات الائتمانية 💳\n" 
        "• `نقدي` - للنقود والسواق 💵\n"
        "• `دين` - للديون والمستحقات 📃\n"
        "• `أشخاص` - للأشخاص 👤\n\n"
        "**أمثلة:**\n"
        "• `بنك الرياض, بنك, 5000`\n"
        "• `بطاقة الائتمان, بطاقة ائتمان, -1000`\n"
        "• `أخي أحمد, أشخاص, 2000`",
        parse_mode='Markdown'
    )
    return NEW_ACCOUNT

@restricted
def handle_new_account(update: Update, context: CallbackContext):
    try:
        data = update.message.text.split(',')
        if len(data) < 3:
            update.message.reply_text("❌ خطأ في الصيغة. يجب إدخال: اسم الحساب, النوع, الرصيد")
            return ConversationHandler.END
            
        account_name = data[0].strip()
        account_type = data[1].strip()
        initial_balance = float(data[2].strip())
        
        accounts, transactions, transfers = load_data()
        
        # التحقق من عدم وجود حساب بنفس الاسم
        if account_name in accounts['اسم الحساب'].values:
            update.message.reply_text("❌ يوجد حساب بنفس ال름 مسبقاً!")
            return ConversationHandler.END
        
        # إضافة الحساب الجديد
        new_account = {
            'اسم الحساب': account_name,
            'النوع': account_type,
            'الرصيد': initial_balance
        }
        
        accounts = pd.concat([accounts, pd.DataFrame([new_account])], ignore_index=True)
        save_data(accounts, transactions, transfers)
        
        update.message.reply_text(
            f"✅ تم إضافة الحساب الجديد بنجاح!\n\n"
            f"🏦 **الحساب:** {account_name}\n"
            f"📋 **النوع:** {account_type}\n"
            f"💵 **الرصيد الأولي:** {initial_balance:,.0f} ريال"
        )
        
    except ValueError:
        update.message.reply_text("❌ الرصيد يجب أن يكون رقماً!")
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
    
    return ConversationHandler.END

@restricted
def account_statement(update: Update, context: CallbackContext):
    accounts, _, _ = load_data()
    
    # جلب الحسابات بدون الإيموجي
    accounts_list = get_accounts_without_emoji(accounts)
    
    # تحويل كل حساب إلى باك-تيك
    accounts_list_backtick = "\n".join([f"`{acc}`" for acc in accounts_list.splitlines()])

    update.message.reply_text(
        "📋 **كشف حساب:**\n\n"
        "أدخل اسم الحساب الذي تريد كشف حسابه:\n\n"
        f"🏦 **الحسابات المتاحة:**\n{accounts_list_backtick}",
        parse_mode='Markdown'
    )
    return CATEGORY


from telegram.utils.helpers import escape_markdown
from telegram.error import BadRequest

@restricted
def handle_account_statement(update: Update, context: CallbackContext):
    try:
        account_input = update.message.text.strip()
        accounts, transactions, transfers = load_data()
        
        # البحث عن اسم الحساب
        account_name = get_account_name(account_input, accounts)
        if not account_name:
            update.message.reply_text("❌ الحساب غير موجود!")
            return ConversationHandler.END
        
        # تنظيف اسم الحساب من الإيموجي للعرض
        cleaned_account_name = re.sub(r'[^\w\s]', '', account_name).strip()
        
        # الحصول على معلومات الحساب
        account_info = accounts[accounts['اسم الحساب'] == account_name].iloc[0]
        current_balance = account_info['الرصيد']
        account_type = account_info['النوع']
        
        # تصفية المعاملات والتحويلات
        account_transactions = transactions[transactions['الحساب'] == account_name]
        outgoing_transfers = transfers[transfers['من حساب'] == account_name]
        incoming_transfers = transfers[transfers['إلى حساب'] == account_name]
        
        # حساب الرصيد الافتتاحي
        total_income = account_transactions[account_transactions['النوع'] == 'دخل']['المبلغ'].sum()
        total_expenses = account_transactions[account_transactions['النوع'] == 'مصروف']['المبلغ'].sum()
        total_incoming_transfers = incoming_transfers['المبلغ'].sum()
        total_outgoing_transfers = outgoing_transfers['المبلغ'].sum()
        
        opening_balance = current_balance + total_expenses - total_income + total_outgoing_transfers - total_incoming_transfers
        
        # إنشاء تقرير منظم
        message = f"📊 *كشف حساب: {cleaned_account_name}*\n"
        message += f"📋 النوع: {account_type}\n"
        message += f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d')}\n"
        message += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        
        message += f"💰 *الرصيد الافتتاحي:* {opening_balance:,.0f} ريال\n\n"
        
        # المعاملات
        message += "💳 *المعاملات*\n"
        message += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        
        if account_transactions.empty:
            message += "لا توجد معاملات\n\n"
        else:
            # الدخل
            income_transactions = account_transactions[account_transactions['النوع'] == 'دخل']
            if not income_transactions.empty:
                message += "↙️ *الدخل:*\n"
                for _, transaction in income_transactions.iterrows():
                    category_escaped = escape_markdown(str(transaction['التصنيف']), version=2)
                    message += f"   + {transaction['المبلغ']:,.0f} ريال - {category_escaped} ({transaction['التاريخ']})\n"
                message += f"   المجموع: +{income_transactions['المبلغ'].sum():,.0f} ريال\n\n"
            
            # المصروفات
            expense_transactions = account_transactions[account_transactions['النوع'] == 'مصروف']
            if not expense_transactions.empty:
                message += "↗️ *المصروفات:*\n"
                for _, transaction in expense_transactions.iterrows():
                    category_escaped = escape_markdown(str(transaction['التصنيف']), version=2)
                    message += f"   - {transaction['المبلغ']:,.0f} ريال - {category_escaped} ({transaction['التاريخ']})\n"
                message += f"   المجموع: -{expense_transactions['المبلغ'].sum():,.0f} ريال\n\n"
        
        # التحويلات
        message += "🔄 *التحويلات*\n"
        message += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        
        if outgoing_transfers.empty and incoming_transfers.empty:
            message += "لا توجد تحويلات\n\n"
        else:
            # التحويلات الواردة
            if not incoming_transfers.empty:
                message += "⬅️ *التحويلات الواردة:*\n"
                for _, transfer in incoming_transfers.iterrows():
                    from_acc_clean = re.sub(r'[^\w\s]', '', transfer['من حساب']).strip()
                    from_acc_escaped = escape_markdown(from_acc_clean, version=2)
                    message += f"   + {transfer['المبلغ']:,.0f} ريال من {from_acc_escaped} ({transfer['التاريخ']})\n"
                message += f"   المجموع: +{incoming_transfers['المبلغ'].sum():,.0f} ريال\n\n"
            
            # التحويلات الصادرة
            if not outgoing_transfers.empty:
                message += "➡️ *التحويلات الصادرة:*\n"
                for _, transfer in outgoing_transfers.iterrows():
                    to_acc_clean = re.sub(r'[^\w\s]', '', transfer['إلى حساب']).strip()
                    to_acc_escaped = escape_markdown(to_acc_clean, version=2)
                    message += f"   - {transfer['المبلغ']:,.0f} ريال إلى {to_acc_escaped} ({transfer['التاريخ']})\n"
                message += f"   المجموع: -{outgoing_transfers['المبلغ'].sum():,.0f} ريال\n\n"
        
        # الملخص المالي
        message += "🧮 *الملخص المالي*\n"
        message += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        message += f"الرصيد الافتتاحي: {opening_balance:,.0f} ريال\n"
        message += f"إجمالي الدخل: +{total_income:,.0f} ريال\n"
        message += f"إجمالي المصروفات: -{total_expenses:,.0f} ريال\n"
        message += f"صافي التحويلات: {total_incoming_transfers - total_outgoing_transfers:+,.0f} ريال\n"
        message += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        message += f"💰 *الرصيد الختامي: {current_balance:,.0f} ريال*"
        
        # تقسيم الرسالة إذا كانت طويلة جداً
        def split_message(text, max_length=4096):
            return [text[i:i+max_length] for i in range(0, len(text), max_length)]
        
        message_parts = split_message(message)
        
        for part in message_parts:
            try:
                update.message.reply_text(part, parse_mode='Markdown')
            except BadRequest:
                # إذا فشل Markdown، أرسل بدون تنسيق
                update.message.reply_text(part)
        
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
        import traceback
        traceback.print_exc()
    
    return ConversationHandler.END

def calculate_budget():
    """حساب الموازنة الإجمالية (مجموع كل الحسابات مطروحاً منها 800000)"""
    accounts, _, _ = load_data()
    total_balance = accounts['الرصيد'].sum()
    budget = total_balance - 800000
    return budget

def main():
    init_excel_file()
    
    updater = Updater(TELEGRAM_BOT_TOKEN)
    dispatcher = updater.dispatcher
    
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(Filters.regex('^➕ إضافة مصروف$'), add_expense),
            MessageHandler(Filters.regex('^💸 إضافة دخل$'), add_income),
            MessageHandler(Filters.regex('^🔄 تحويل بين الحسابات$'), transfer_money),
            MessageHandler(Filters.regex('^🏦 إضافة حساب جديد$'), add_new_account),
            MessageHandler(Filters.regex('^📋 كشف حساب$'), account_statement),
            MessageHandler(Filters.regex('^🏦 معالجة رسالة بنك$'), process_bank_message)
        ],
        states={
            ADD_EXPENSE: [MessageHandler(Filters.text & ~Filters.command, handle_add_expense)],
            ADD_INCOME: [MessageHandler(Filters.text & ~Filters.command, handle_add_income)],
            TRANSFER: [MessageHandler(Filters.text & ~Filters.command, handle_transfer)],
            TRANSFER_CONFIRM: [MessageHandler(Filters.text & ~Filters.command, handle_transfer_confirm)],
            NEW_ACCOUNT: [MessageHandler(Filters.text & ~Filters.command, handle_new_account)],
            CATEGORY: [MessageHandler(Filters.text & ~Filters.command, handle_account_statement)],
            PROCESS_BANK_MSG: [MessageHandler(Filters.text & ~Filters.command, handle_bank_message)],
            CONFIRM_TRANSACTION: [MessageHandler(Filters.text & ~Filters.command, handle_transaction_confirmation)]
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