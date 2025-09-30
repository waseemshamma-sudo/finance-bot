import os
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
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
ADD_EXPENSE, ADD_INCOME, TRANSFER, NEW_ACCOUNT, CATEGORY, MANAGE_USERS, AUTO_EXTRACT, TRANSFER_CONFIRM = range(8)
EXCEL_FILE = "financial_tracker.xlsx"

# قاموس الحسابات الافتراضي
DEFAULT_ACCOUNTS_MAP = {
    '6600': '💳 ماستر',
    '3373': '💳 ماستر', 
    '5805': '💳 ماستر',
    '1127': '🏛 إس تي سي ',
    '2842': '🏛 راجحي ',
    '0103': '🏛 أهلي 121',
    '1534': '🏛 أهلي 121',
    '0700': '🏛 أهلي 136',
    '8825': '🏛 أهلي 136'
}

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
            
            # إضافة ورقة جديدة للمستخدمين المصرح لهم
            users_data = {
                'user_id': [123456789],  # استبدل بآيدي الخاص بك
                'username': ['admin'],
                'permission_level': ['admin']  # admin, user
            }
            pd.DataFrame(users_data).to_excel(writer, sheet_name='المستخدمين', index=False)

def load_data():
    accounts = pd.read_excel(EXCEL_FILE, sheet_name='الحسابات')
    transactions = pd.read_excel(EXCEL_FILE, sheet_name='المعاملات')
    transfers = pd.read_excel(EXCEL_FILE, sheet_name='التحويلات')
    
    # تحميل بيانات المستخدمين إذا كانت الورقة موجودة
    try:
        users = pd.read_excel(EXCEL_FILE, sheet_name='المستخدمين')
    except:
        users = pd.DataFrame(columns=['user_id', 'username', 'permission_level'])
    
    return accounts, transactions, transfers, users

def save_data(accounts, transactions, transfers, users=None):
    with pd.ExcelWriter(EXCEL_FILE) as writer:
        accounts.to_excel(writer, sheet_name='الحسابات', index=False)
        transactions.to_excel(writer, sheet_name='المعاملات', index=False)
        transfers.to_excel(writer, sheet_name='التحويلات', index=False)
        
        # حفظ بيانات المستخدمين إذا تم توفيرها
        if users is not None:
            users.to_excel(writer, sheet_name='المستخدمين', index=False)

# دالة للتحقق من صلاحيات المستخدم
def check_user_permission(user_id, required_level='user'):
    _, _, _, users = load_data()
    
    # إذا لم يكن هناك مستخدمين مسجلين، اسمح للجميع بالوصول (للتشغيل الأولي)
    if users.empty:
        return True
    
    user = users[users['user_id'] == user_id]
    
    if user.empty:
        return False
    
    user_level = user.iloc[0]['permission_level']
    
    if required_level == 'admin':
        return user_level == 'admin'
    else:
        return user_level in ['admin', 'user']

# دالة للتحقق من صلاحية المشرف
def is_admin(user_id):
    return check_user_permission(user_id, 'admin')

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

# تعديل دالة start للتحقق من الصلاحية
def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not check_user_permission(user_id):
        update.message.reply_text("❌ ليس لديك صلاحية للوصول إلى هذا البوت.")
        return
    
    keyboard = [
        ['➕ إضافة مصروف', '💸 إضافة دخل'], 
        ['🔄 تحويل بين الحسابات', '📊 عرض الحسابات'], 
        ['📈 عرض المصروفات', '🏦 إضافة حساب جديد'],
        ['📋 كشف حساب', '📨 معالجة رسالة']
    ]
    
    # إضافة زر إدارة المستخدمين للمشرفين فقط
    if is_admin(user_id):
        keyboard.append(['👥 إدارة المستخدمين'])
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    update.message.reply_text(
        '👋 مرحباً! أنا بوت إدارة الحسابات الشخصية. \n\n'
        '📌 يمكنني مساعدتك في:\n'
        '• تسجيل المصروفات والدخل 💰\n'
        '• تحويل الأموال بين الحسابات 🔄\n'
        '• متابعة أرصدة حساباتك 📊\n'
        '• إنشاء تقارير مالية 📈\n'
        '• معالجة الرسائل النصية تلقائياً 📨\n\n'
        'اختر من الخيارات في لوحة المفاتيح: 👇', 
        reply_markup=reply_markup
    )

# نظام استخراج المعاملات من الرسائل النصية
class FinancialTransactionProcessor:
    def __init__(self):
        self.patterns = {
            'transaction_type': [
                (r'POS Purchase|شراء-POS|شراء', 'expense'),
                (r'Outgoing.*transfer|تحويل صادر', 'expense'),
                (r'Reverse Transaction|إسترداد مبلغ', 'income'),
                (r'Credit Transfer|تحويل وارد', 'income'),
                (r'Online Purchase|شراء إنترنت|شراء اون لاين', 'expense')
            ],
            'amount': r'Amount[:]?\s*([\d,.]+)\s*SAR|مبلغ[:\s]*([\d,.]+)\s*SAR|بـ[:\s]*([\d,.]+)\s*SAR',
            'date': r'On[:]?\s*(\d{2}/\d{2}/\d{2})|On[:]?\s*(\d{2}/\d{2}/\d{4})|تاريخ[:\s]*(\d{2}/\d{2}/\d{2})|في[:\s]*(\d{2}/\d{2}/\d{2})',
            'merchant': r'At\s*(.+?)\s*(?=By|On|$)|من\s*(.+?)\s*(?=إئتمانية|بطاقة|التاريخ|$)',
            'payment_method': r'By[:\s]*(.+?)\s*(?=On|$)|بطاقة[:\s]*(.+?)\s*(?=من|التاريخ|$)',
            'card_number': r'\*{2,3}(\d{4})'
        }
    
    def extract_info(self, text: str) -> dict:
        """استخراج المعلومات من النص"""
        result = {
            'type': self._determine_transaction_type(text),
            'amount': self._extract_value(text, self.patterns['amount']),
            'date': self._extract_date(text),
            'merchant': self._extract_value(text, self.patterns['merchant']),
            'payment_method': self._extract_value(text, self.patterns['payment_method']),
            'card_number': self._extract_value(text, self.patterns['card_number']),
            'original_text': text
        }
        return result
    
    def _determine_transaction_type(self, text: str) -> str:
        """تحديد نوع المعاملة (إيراد أو مصروف)"""
        for pattern, t_type in self.patterns['transaction_type']:
            if re.search(pattern, text, re.IGNORECASE):
                return t_type
        return 'unknown'
    
    def _extract_value(self, text: str, pattern: str) -> str:
        """استخراج قيمة من النص باستخدام نمط محدد"""
        matches = re.search(pattern, text, re.IGNORECASE)
        if matches:
            # إرجاع أول مجموعة غير فارغة
            for group in matches.groups():
                if group and group.strip():
                    return group.strip()
        return "غير محدد"
    
    def _extract_date(self, text: str) -> str:
        """استخراج وتنسيق التاريخ"""
        matches = re.search(self.patterns['date'], text)
        if matches:
            for group in matches.groups():
                if group:
                    try:
                        # تحويل التاريخ إلى صيغة موحدة
                        if len(group.split('/')[2]) == 2:
                            date_obj = datetime.strptime(group, '%d/%m/%y')
                        else:
                            date_obj = datetime.strptime(group, '%d/%m/%Y')
                        return date_obj.strftime('%Y-%m-%d')
                    except:
                        return group
        return datetime.now().strftime('%Y-%m-%d')
    
    def process_multiple_transactions(self, text: str) -> list:
        """معالجة نص يحتوي على multiple transactions"""
        # تقسيم النص إلى معاملات منفصلة
        transactions = []
        
        # محاولة استخراج معاملة واحدة أولاً
        transaction = self.extract_info(text)
        if transaction['type'] != 'unknown':
            return [transaction]
        
        # إذا لم تنجح، تجربة تقسيم النص
        patterns = [
            r'POS Purchase',
            r'Outgoing.*transfer',
            r'Reverse Transaction',
            r'Credit Transfer',
            r'Online Purchase',
            r'شراء-POS',
            r'إسترداد مبلغ',
            r'تحويل',
            r'شراء إنترنت',
            r'شراء اون لاين'
        ]
        
        combined_pattern = '|'.join(patterns)
        transaction_starts = list(re.finditer(combined_pattern, text, re.IGNORECASE))
        
        if not transaction_starts:
            return []
        
        # تقسيم النص بناء على مواقع بدء المعاملات
        for i, match in enumerate(transaction_starts):
            start_pos = match.start()
            if i < len(transaction_starts) - 1:
                end_pos = transaction_starts[i+1].start()
                transaction_text = text[start_pos:end_pos]
            else:
                transaction_text = text[start_pos:]
            
            if transaction_text.strip():
                transaction = self.extract_info(transaction_text)
                if transaction['type'] != 'unknown':
                    transactions.append(transaction)
        
        return transactions

# دالة لمعالجة الرسائل النصية التلقائية
def auto_extract_transaction(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not check_user_permission(user_id):
        update.message.reply_text("❌ ليس لديك صلاحية للوصول إلى هذا البوت.")
        return
    
    update.message.reply_text(
        "📨 **معالجة الرسائل النصية:**\n\n"
        "ألصق الرسالة النصية التي تريد استخراج المعاملة منها:\n\n"
        "سأحاول استخراج المعلومات تلقائياً وأطلب منك التأكيد قبل التسجيل.",
        parse_mode='Markdown'
    )
    return AUTO_EXTRACT

def handle_auto_extract(update: Update, context: CallbackContext):
    try:
        text = update.message.text
        processor = FinancialTransactionProcessor()
        transactions = processor.process_multiple_transactions(text)
        
        if not transactions:
            update.message.reply_text("❌ لم أتمكن من استخراج أي معاملة من النص.")
            return ConversationHandler.END
        
        # حفظ المعاملات المستخرجة مؤقتاً
        context.user_data['extracted_transactions'] = transactions
        context.user_data['current_transaction_index'] = 0
        
        # عرض أول معاملة للموافقة
        return show_extracted_transaction(update, context)
        
    except Exception as e:
        update.message.reply_text(f"❌ خطأ في معالجة النص: {str(e)}")
        return ConversationHandler.END

def show_extracted_transaction(update: Update, context: CallbackContext):
    transactions = context.user_data['extracted_transactions']
    index = context.user_data['current_transaction_index']
    
    if index >= len(transactions):
        update.message.reply_text("✅ تم معالجة جميع المعاملات.")
        return ConversationHandler.END
    
    transaction = transactions[index]
    
    message = f"📄 **المعاملة {index + 1} من {len(transactions)}:**\n\n"
    message += f"📊 **النوع:** {'مصروف' if transaction['type'] == 'expense' else 'إيراد'}\n"
    message += f"💰 **المبلغ:** {transaction['amount']} ريال\n"
    message += f"📅 **التاريخ:** {transaction['date']}\n"
    message += f"🏪 **التاجر:** {transaction['merchant']}\n"
    message += f"💳 **طريقة الدفع:** {transaction['payment_method']}\n"
    message += f"🔢 **رقم البطاقة:** {transaction['card_number']}\n\n"
    message += "هل تريد إضافة هذه المعاملة؟ (نعم/لا/تخطي الكل)"
    
    # حفظ الفهرس الحالي
    context.user_data['current_transaction_index'] = index
    
    update.message.reply_text(message, parse_mode='Markdown')
    return AUTO_EXTRACT

def handle_extraction_confirmation(update: Update, context: CallbackContext):
    user_response = update.message.text.strip().lower()
    transactions = context.user_data['extracted_transactions']
    index = context.user_data['current_transaction_index']
    
    if user_response in ['تخطي الكل', 'skip all', 'كل', 'all']:
        update.message.reply_text("✅ تم تخطي جميع المعاملات المتبقية.")
        return ConversationHandler.END
    
    if user_response in ['نعم', 'yes', 'y', 'موافق', 'أجل']:
        # إضافة المعاملة
        transaction = transactions[index]
        return add_extracted_transaction(update, context, transaction)
    
    if user_response in ['لا', 'no', 'n', 'رفض']:
        # تخطي هذه المعاملة
        update.message.reply_text("⏭️ تم تخطي هذه المعاملة.")
    
    # الانتقال إلى المعاملة التالية
    context.user_data['current_transaction_index'] += 1
    return show_extracted_transaction(update, context)

def add_extracted_transaction(update: Update, context: CallbackContext, transaction: dict):
    try:
        accounts, transactions_df, transfers, _ = load_data()
        
        # تحديد الحساب المناسب بناءً على طريقة الدفع
        account_name = None
        
        # استخدام القاموس لتحديد الحساب المناسب
        if transaction['card_number'] != "غير محدد" and transaction['card_number'] in DEFAULT_ACCOUNTS_MAP:
            account_name = DEFAULT_ACCOUNTS_MAP[transaction['card_number']]
        
        # إذا لم يتم العثور على حساب، استخدام الحساب الافتراضي
        if not account_name:
            account_name = "💳 بطاقة الائتمان"  # الحساب الافتراضي
        
        # التحقق من وجود الحساب
        if account_name not in accounts['اسم الحساب'].values:
            update.message.reply_text(f"❌ الحساب {account_name} غير موجود في النظام!")
            context.user_data['current_transaction_index'] += 1
            return show_extracted_transaction(update, context)
        
        # معالجة المبلغ
        try:
            amount = float(transaction['amount'].replace(',', ''))
        except:
            amount = 0
        
        if amount <= 0:
            update.message.reply_text("❌ المبلغ غير صالح.")
            context.user_data['current_transaction_index'] += 1
            return show_extracted_transaction(update, context)
        
        # إضافة المعاملة
        if transaction['type'] == 'expense':
            # مصروف
            account_index = accounts[accounts['اسم الحساب'] == account_name].index
            if account_index.empty:
                update.message.reply_text("❌ لم يتم العثور على الحساب.")
                context.user_data['current_transaction_index'] += 1
                return show_extracted_transaction(update, context)
                
            accounts.at[account_index[0], 'الرصيد'] -= amount
            
            new_transaction = {
                'التاريخ': transaction['date'],
                'النوع': 'مصروف',
                'المبلغ': amount,
                'الحساب': account_name,
                'التصنيف': transaction['merchant'] if transaction['merchant'] != "غير محدد" else "شراء"
            }
        else:
            # إيراد
            account_index = accounts[accounts['اسم الحساب'] == account_name].index
            if account_index.empty:
                update.message.reply_text("❌ لم يتم العثور على الحساب.")
                context.user_data['current_transaction_index'] += 1
                return show_extracted_transaction(update, context)
                
            accounts.at[account_index[0], 'الرصيد'] += amount
            
            new_transaction = {
                'التاريخ': transaction['date'],
                'النوع': 'دخل',
                'المبلغ': amount,
                'الحساب': account_name,
                'التصنيف': transaction['merchant'] if transaction['merchant'] != "غير محدد" else "استرداد"
            }
        
        transactions_df = pd.concat([transactions_df, pd.DataFrame([new_transaction])], ignore_index=True)
        save_data(accounts, transactions_df, transfers)
        
        # الحصول على الرصيد الجديد
        new_balance = accounts.at[account_index[0], 'الرصيد']
        
        update.message.reply_text(
            f"✅ تم إضافة المعاملة بنجاح!\n"
            f"📊 الرصيد الجديد: {new_balance:,.2f} ريال"
        )
        
    except Exception as e:
        update.message.reply_text(f"❌ خطأ في إضافة المعاملة: {str(e)}")
    
    # الانتقال إلى المعاملة التالية
    context.user_data['current_transaction_index'] += 1
    return show_extracted_transaction(update, context)

# دالة إدارة المستخدمين
def manage_users(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        update.message.reply_text("❌ ليس لديك صلاحية لإدارة المستخدمين.")
        return ConversationHandler.END
    
    update.message.reply_text(
        "👥 **إدارة المستخدمين:**\n\n"
        "اختر أحد الخيارات:\n"
        "• `اضافة مستخدم` - لإضافة مستخدم جديد\n"
        "• `عرض المستخدمين` - لعرض جميع المستخدمين\n"
        "• `حذف مستخدم` - لحذف مستخدم\n\n"
        "أو أرسل `إلغاء` للعودة.",
        parse_mode='Markdown'
    )
    return MANAGE_USERS

# معالجة أوامر إدارة المستخدمين
def handle_manage_users(update: Update, context: CallbackContext):
    user_input = update.message.text.strip()
    
    if user_input == 'إلغاء':
        update.message.reply_text("❌ تم الإلغاء.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    if user_input == 'اضافة مستخدم':
        update.message.reply_text(
            "➕ **إضافة مستخدم جديد:**\n\n"
            "أدخل بيانات المستخدم بالصيغة التالية:\n"
            "`user_id, username, permission_level`\n\n"
            "**مثال:**\n"
            "`123456789, user1, user`",
            parse_mode='Markdown'
        )
        context.user_data['user_action'] = 'add_user'
        return MANAGE_USERS
    
    elif user_input == 'عرض المستخدمين':
        _, _, _, users = load_data()
        
        if users.empty:
            update.message.reply_text("📭 لا يوجد مستخدمين مسجلين.")
            return MANAGE_USERS
        
        message = "👥 **المستخدمون المسجلون:**\n\n"
        for _, user in users.iterrows():
            message += f"• ID: {user['user_id']} - @{user['username']} - {user['permission_level']}\n"
        
        update.message.reply_text(message, parse_mode='Markdown')
        return MANAGE_USERS
    
    elif user_input == 'حذف مستخدم':
        update.message.reply_text(
            "🗑️ **حذف مستخدم:**\n\n"
            "أدخل معرف المستخدم الذي تريد حذفه:",
            parse_mode='Markdown'
        )
        context.user_data['user_action'] = 'delete_user'
        return MANAGE_USERS
    
    else:
        # معالجة الإدخالات المباشرة
        if 'user_action' in context.user_data:
            action = context.user_data['user_action']
            
            if action == 'add_user':
                return handle_add_user(update, context)
            elif action == 'delete_user':
                return handle_delete_user(update, context)
        
        update.message.reply_text("❌ أمر غير معروف. اختر من الخيارات المتاحة.")
        return MANAGE_USERS

# معالجة إضافة مستخدم
def handle_add_user(update: Update, context: CallbackContext):
    try:
        data = update.message.text.split(',')
        if len(data) < 3:
            update.message.reply_text("❌ خطأ في الصيغة. يجب إدخال: user_id, username, permission_level")
            return MANAGE_USERS
            
        user_id = int(data[0].strip())
        username = data[1].strip()
        permission_level = data[2].strip()
        
        if permission_level not in ['admin', 'user']:
            update.message.reply_text("❌ مستوى الصلاحية يجب أن يكون 'admin' أو 'user'")
            return MANAGE_USERS
        
        accounts, transactions, transfers, users = load_data()
        
        # التحقق من عدم وجود مستخدم بنفس الـ ID
        if user_id in users['user_id'].values:
            update.message.reply_text("❌ يوجد مستخدم بنفس المعرف مسبقاً!")
            return MANAGE_USERS
        
        # إضافة المستخدم الجديد
        new_user = {
            'user_id': user_id,
            'username': username,
            'permission_level': permission_level
        }
        
        users = pd.concat([users, pd.DataFrame([new_user])], ignore_index=True)
        save_data(accounts, transactions, transfers, users)
        
        update.message.reply_text(
            f"✅ تم إضافة المستخدم بنجاح!\n\n"
            f"👤 **المستخدم:** {username}\n"
            f"🆔 **المعرف:** {user_id}\n"
            f"🎫 **الصلاحية:** {permission_level}"
        )
        
        # مسح حالة الإجراء
        if 'user_action' in context.user_data:
            del context.user_data['user_action']
            
    except ValueError:
        update.message.reply_text("❌ معرف المستخدم يجب أن يكون رقماً!")
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
    
    return MANAGE_USERS

# معالجة حذف مستخدم
def handle_delete_user(update: Update, context: CallbackContext):
    try:
        user_id = int(update.message.text.strip())
        
        accounts, transactions, transfers, users = load_data()
        
        # التحقق من وجود المستخدم
        if user_id not in users['user_id'].values:
            update.message.reply_text("❌ المستخدم غير موجود!")
            return MANAGE_USERS
        
        # حذف المستخدم
        users = users[users['user_id'] != user_id]
        save_data(accounts, transactions, transfers, users)
        
        update.message.reply_text(f"✅ تم حذف المستخدم ذو المعرف {user_id} بنجاح!")
        
        # مسح حالة الإجراء
        if 'user_action' in context.user_data:
            del context.user_data['user_action']
            
    except ValueError:
        update.message.reply_text("❌ معرف المستخدم يجب أن يكون رقماً!")
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
    
    return MANAGE_USERS

# دالة عرض الحسابات
def show_accounts(update: Update, context: CallbackContext):
    if not check_user_permission(update.effective_user.id):
        update.message.reply_text("❌ ليس لديك صلاحية للوصول إلى هذا البوت.")
        return
    
    accounts, _, _, _ = load_data()
    
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

# دالة عرض المصروفات
def show_expenses(update: Update, context: CallbackContext):
    if not check_user_permission(update.effective_user.id):
        update.message.reply_text("❌ ليس لديك صلاحية للوصول إلى هذا البوت.")
        return
    
    _, transactions, _, _ = load_data()
    
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

# دالة إضافة مصروف
def add_expense(update: Update, context: CallbackContext):
    if not check_user_permission(update.effective_user.id):
        update.message.reply_text("❌ ليس لديك صلاحية للوصول إلى هذا البوت.")
        return
    
    accounts, _, _, _ = load_data()
    
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

# دالة إضافة دخل
def add_income(update: Update, context: CallbackContext):
    if not check_user_permission(update.effective_user.id):
        update.message.reply_text("❌ ليس لديك صلاحية للوصول إلى هذا البوت.")
        return
    
    accounts, _, _, _ = load_data()
    
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

# دالة تحويل الأموال
def transfer_money(update: Update, context: CallbackContext):
    if not check_user_permission(update.effective_user.id):
        update.message.reply_text("❌ ليس لديك صلاحية للوصول إلى هذا البوت.")
        return
    
    accounts, _, _, _ = load_data()
    
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

# دالة إضافة حساب جديد
def add_new_account(update: Update, context: CallbackContext):
    if not check_user_permission(update.effective_user.id):
        update.message.reply_text("❌ ليس لديك صلاحية للوصول إلى هذا البوت.")
        return
    
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

# دالة كشف الحساب
def account_statement(update: Update, context: CallbackContext):
    if not check_user_permission(update.effective_user.id):
        update.message.reply_text("❌ ليس لديك صلاحية للوصول إلى هذا البوت.")
        return
    
    accounts, _, _, _ = load_data()
    
    accounts_list = get_accounts_without_emoji(accounts)
    
    update.message.reply_text(
        "📋 **كشف حساب:**\n\n"
        "أدخل اسم الحساب الذي تريد كشف حسابه:\n\n"
        f"🏦 **الحسابات المتاحة:**\n{accounts_list}",
        parse_mode='Markdown'
    )
    return CATEGORY

# معالجة إضافة مصروف
def handle_add_expense(update: Update, context: CallbackContext):
    if not check_user_permission(update.effective_user.id):
        update.message.reply_text("❌ ليس لديك صلاحية للوصول إلى هذا البوت.")
        return ConversationHandler.END
    
    try:
        data = update.message.text.split(',')
        if len(data) < 3:
            update.message.reply_text("❌ خطأ في الصيغة. يجب إدخال: التصنيف, المبلغ, الحساب")
            return ConversationHandler.END
            
        category = data[0].strip()
        amount = float(data[1].strip())
        account_input = data[2].strip()
        
        accounts, transactions, transfers, _ = load_data()
        
        # البحث عن اسم الحساب باستخدام الدالة الجديدة
        account_name = get_account_name(account_input, accounts)
        if not account_name:
            update.message.reply_text("❌ الحساب غير موجود!")
            return ConversationHandler.END
        
        # تحديث رصيد الحساب
        account_index = accounts[accounts['اسم الحساب'] == account_name].index
        accounts.at[account_index[0], 'الرصيد'] -= amount
        new_balance = accounts.at[account_index[0], 'الرصيد']  # الحصول على الرصيد الجديد
        
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
        update.message.reply_text(
            f"✅ تم تسجيل مصروف {amount} ريال من {account_name} للتصنيف {category}\n"
            f"📊 الرصيد الحالي: {new_balance:,.1f} ريال"
        )
    except ValueError:
        update.message.reply_text("❌ المبلغ يجب أن يكون رقماً!")
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
    
    return ConversationHandler.END

# معالجة إضافة دخل
def handle_add_income(update: Update, context: CallbackContext):
    if not check_user_permission(update.effective_user.id):
        update.message.reply_text("❌ ليس لديك صلاحية للوصول إلى هذا البوت.")
        return ConversationHandler.END
    
    try:
        data = update.message.text.split(',')
        if len(data) < 3:
            update.message.reply_text("❌ خطأ في الصيغة. يجب إدخال: المصدر, المبلغ, الحساب")
            return ConversationHandler.END
            
        source = data[0].strip()
        amount = float(data[1].strip())
        account_input = data[2].strip()
        
        accounts, transactions, transfers, _ = load_data()
        
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
        update.message.reply_text(
            f"✅ تم تسجيل دخل {amount} ريال إلى {account_name} من {source}\n"
            f"📊 الرصيد الحالي: {new_balance:,.1f} ريال"
        )
    except ValueError:
        update.message.reply_text("❌ المبلغ يجب أن يكون رقماً!")
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
    
    return ConversationHandler.END

# معالجة التحويل
def handle_transfer(update: Update, context: CallbackContext):
    if not check_user_permission(update.effective_user.id):
        update.message.reply_text("❌ ليس لديك صلاحية للوصول إلى هذا البوت.")
        return ConversationHandler.END
    
    try:
        data = update.message.text.split(',')
        if len(data) < 3:
            update.message.reply_text("❌ خطأ في الصيغة. يجب إدخال: من حساب, إلى حساب, المبلغ")
            return ConversationHandler.END
            
        from_acc_input = data[0].strip()
        to_acc_input = data[1].strip()
        amount = float(data[2].strip())
        
        accounts, transactions, transfers, _ = load_data()
        
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
                f"💸 المبلغ المطلوب: {amount} ريal\n"
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

# دالة تنفيذ التحويل
def execute_transfer(update, from_acc, to_acc, amount, accounts, transactions, transfers):
    # تحديث الرصيد
    from_index = accounts[accounts['اسم الحساب'] == from_acc].index
    to_index = accounts[accounts['اسم الحساب'] == to_acc].index
    
    accounts.at[from_index[0], 'الرصido'] -= amount
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

# معالجة إضافة حساب جديد
def handle_new_account(update: Update, context: CallbackContext):
    if not check_user_permission(update.effective_user.id):
        update.message.reply_text("❌ ليس لديك صلاحية للوصول إلى هذا البوت.")
        return ConversationHandler.END
    
    try:
        data = update.message.text.split(',')
        if len(data) < 3:
            update.message.reply_text("❌ خطأ في الصيغة. يجب إدخال: اسم الحساب, النوع, الرصيد")
            return ConversationHandler.END
            
        account_name = data[0].strip()
        account_type = data[1].strip()
        initial_balance = float(data[2].strip())
        
        accounts, transactions, transfers, _ = load_data()
        
        # التحقق من عدم وجود حساب بنفس الاسم
        if account_name in accounts['اسم الحساب'].values:
            update.message.reply_text("❌ يوجد حساب بنفس الاسم مسبقاً!")
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

# معالجة كشف الحساب
def handle_account_statement(update: Update, context: CallbackContext):
    if not check_user_permission(update.effective_user.id):
        update.message.reply_text("❌ ليس لديك صلاحية للوصول إلى هذا البوت.")
        return ConversationHandler.END
    
    try:
        account_input = update.message.text.strip()
        accounts, transactions, transfers, _ = load_data()
        
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
        
        # حساب الرصيد الافتتاحي (مجموع الدخل - المصروفات + التحويلات الواردة - الصادرة)
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
                    message += f"   + {transaction['المبلغ']:,.0f} ريال - {transaction['التصنيف']} ({transaction['التاريخ']})\n"
                message += f"   المجموع: +{income_transactions['المبلغ'].sum():,.0f} ريال\n\n"
            
            # المصروفات
            expense_transactions = account_transactions[account_transactions['النوع'] == 'مصروف']
            if not expense_transactions.empty:
                message += "↗️ *المصروفات:*\n"
                for _, transaction in expense_transactions.iterrows():
                    message += f"   - {transaction['المبلغ']:,.0f} ريال - {transaction['التصنيف']} ({transaction['التاريخ']})\n"
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
                    message += f"   + {transfer['المبلغ']:,.0f} ريال من {from_acc_clean} ({transfer['التاريخ']})\n"
                message += f"   المجموع: +{incoming_transfers['المبلغ'].sum():,.0f} ريال\n\n"
            
            # التحويلات الصادرة
            if not outgoing_transfers.empty:
                message += "➡️ *التحويلات الصادرة:*\n"
                for _, transfer in outgoing_transfers.iterrows():
                    to_acc_clean = re.sub(r'[^\w\s]', '', transfer['إلى حساب']).strip()
                    message += f"   - {transfer['المبلغ']:,.0f} ريال إلى {to_acc_clean} ({transfer['التاريخ']})\n"
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
        
        update.message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
    
    return ConversationHandler.END

# دالة الإلغاء
def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("❌ تم الإلغاء.")
    return ConversationHandler.END

# دالة معالجة الرسائل العامة
def handle_message(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if not check_user_permission(user_id):
        update.message.reply_text("❌ ليس لديك صلاحية للوصول إلى هذا البوت.")
        return
    
    text = update.message.text
    if text == '📊 عرض الحسابات':
        show_accounts(update, context)
    elif text == '📈 عرض المصروفات':
        show_expenses(update, context)
    elif text == '🏦 إضافة حساب جديد':
        add_new_account(update, context)
    elif text == '👥 إدارة المستخدمين':
        manage_users(update, context)
    elif text == '📨 معالجة رسالة':
        auto_extract_transaction(update, context)
    elif text == '📋 كشف حساب':
        account_statement(update, context)
    else:
        update.message.reply_text("👋 استخدم الأزرار في لوحة المفاتيح للتفاعل مع البوت")

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
            MessageHandler(Filters.regex('^👥 إدارة المستخدمين$'), manage_users),
            MessageHandler(Filters.regex('^📨 معالجة رسالة$'), auto_extract_transaction)
        ],
        states={
            ADD_EXPENSE: [MessageHandler(Filters.text & ~Filters.command, handle_add_expense)],
            ADD_INCOME: [MessageHandler(Filters.text & ~Filters.command, handle_add_income)],
            TRANSFER: [MessageHandler(Filters.text & ~Filters.command, handle_transfer)],
            TRANSFER_CONFIRM: [MessageHandler(Filters.text & ~Filters.command, handle_transfer_confirm)],
            NEW_ACCOUNT: [MessageHandler(Filters.text & ~Filters.command, handle_new_account)],
            CATEGORY: [MessageHandler(Filters.text & ~Filters.command, handle_account_statement)],
            MANAGE_USERS: [MessageHandler(Filters.text & ~Filters.command, handle_manage_users)],
            AUTO_EXTRACT: [
                MessageHandler(Filters.text & ~Filters.command, handle_auto_extract),
                MessageHandler(Filters.text & ~Filters.command, handle_extraction_confirmation)
            ]
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