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
ALLOWED_USER_IDS = list(map(int, os.getenv("ALLOWED_USER_IDS", "").split(','))) if os.getenv("ALLOWED_USER_IDS") else []

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("❌ لم يتم العثور على TELEGRAM_BOT_TOKEN في ملف البيئة")

# حالات المحادثة
ADD_EXPENSE, ADD_INCOME, TRANSFER, NEW_ACCOUNT, CATEGORY, BANK_MESSAGE, ACCOUNT_NAME, TRANSFER_TO_ACCOUNT, TRANSFER_CONFIRM = range(9)
EXCEL_FILE = "financial_tracker.xlsx"

# دالة للتحقق من صلاحية المستخدم
def allowed_user_only(func):
    def wrapper(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id not in ALLOWED_USER_IDS:
            update.message.reply_text("❌ غير مصرح لك باستخدام هذا البوت.")
            return ConversationHandler.END
        return func(update, context, *args, **kwargs)
    return wrapper

# دالة جديدة للتعامل مع أسماء الحسابات مع الإيموجي
def get_account_name(user_input, accounts_df):
    """
    البحث عن اسم الحساب مع أو بدون الإيموجي
    """
    user_input = user_input.strip().lower()
    
    if not user_input:
        return None
    
    # البحث الدقيق أولاً (بدون إيموجي)
    for account_name in accounts_df['اسم الحساب']:
        cleaned_name = re.sub(r'[^\w\s]', '', account_name).strip().lower()
        if user_input == cleaned_name:
            return account_name
    
    # البحث الجزئي (بدون إيموجي)
    for account_name in accounts_df['اسم الحساب']:
        cleaned_name = re.sub(r'[^\w\s]', '', account_name).strip().lower()
        if user_input in cleaned_name:
            return account_name
    
    # البحث بالإيموجي
    for account_name in accounts_df['اسم الحساب']:
        if user_input in account_name.lower():
            return account_name
    
    # البحث بالأرقام فقط
    if user_input.isdigit():
        for account_name in accounts_df['اسم الحساب']:
            numbers_in_name = re.findall(r'\d+', account_name)
            if user_input in numbers_in_name:
                return account_name
    
    return None

def show_available_accounts(update: Update, accounts_df):
    """عرض الحسابات المتاحة للمستخدم"""
    accounts_list = get_accounts_without_emoji(accounts_df)
    update.message.reply_text(
        f"🏦 **الحسابات المتاحة:**\n{accounts_list}\n\n"
        "📋 الرجاء إدخال اسم الحساب أو جزء منه:",
        parse_mode='Markdown'
    )

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

# دالة لاستخراج المبلغ من رسالة البنك
def extract_amount_from_bank_message(message):
    """
    استخراج المبلغ من رسالة البنك باستخدام التعابير النمطية
    """
    try:
        # تحويل الرسالة إلى صيغة قابلة للبحث
        message_lower = message.lower().replace(',', '')
        
        # أنماط للبحث عن مبلغ المعاملة (ليس الرصيد المتبقي)
        patterns = [
            # أنماط لمبلغ المعاملة الرئيسي (بعد Amount)
            r'amount\s*[:=]?\s*([\d,]+\.?\d*)',
            r'monto\s*[:=]?\s*([\d,]+\.?\d*)',
            r'مبلغ\s*[:=]?\s*([\d,]+\.?\d*)',
            r'قيمة\s*[:=]?\s*([\d,]+\.?\d*)',
            r'المبلغ\s*[:=]?\s*([\d,]+\.?\d*)',
            
            # أنماط للبحث عن أي مبلغ يظهر بعد كلمات محددة
            r'purchase\s+([\d,]+\.?\d*)',
            r'شراء\s+([\d,]+\.?\d*)',
            r'عملية\s+([\d,]+\.?\d*)',
            r'صرف\s+([\d,]+\.?\d*)',
            
            # أنماط عامة للبحث عن المبالغ مع عملة
            r'(\d+\.?\d*)\s*(?:ريال|ر\.س|sar|ر س)',
            r'(\d+\.?\d*)\s*(?:ر\.يال|ريال|ر\s*ي\s*ا\s*ل)',
            
            # أنماط للبحث عن أرقام عائمة
            r'\b(\d+\.\d{2})\b',  # أرقام مثل 35.54
        ]
        
        # البحث عن مبلغ المعاملة
        transaction_amount = None
        for pattern in patterns:
            matches = re.findall(pattern, message_lower)
            if matches:
                # أخذ أول مبلغ (عادة هو مبلغ المعاملة)
                transaction_amount = float(matches[0])
                print(f"وجد المبلغ {transaction_amount} بالنمط: {pattern}")  # للتdebug
                break
        
        # إذا لم نجد مبلغ معاملة، نبحث عن أي مبلغ
        if transaction_amount is None:
            # البحث عن جميع المبالغ في الرسالة
            all_amounts = re.findall(r'(\d+\.?\d*)', message_lower)
            if all_amounts:
                amounts = [float(amount) for amount in all_amounts if float(amount) > 0]
                
                if amounts:
                    # نحاول تحديد مبلغ المعاملة (عادة يكون أصغر مبلغ ليس رصيداً)
                    if len(amounts) > 1:
                        # نستثني المبالغ الكبيرة (التي قد تكون أرصدة أو حدود)
                        small_amounts = [amt for amt in amounts if amt < 1000]
                        if small_amounts:
                            transaction_amount = min(small_amounts)
                        else:
                            transaction_amount = min(amounts)
                    else:
                        transaction_amount = amounts[0]
        
        return transaction_amount
        
    except Exception as e:
        print(f"خطأ في استخراج المبلغ: {e}")
        return None


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
@allowed_user_only
def start(update: Update, context: CallbackContext):
    keyboard = [
        ['➕ إضافة مصروف', '💸 إضافة دخل'], 
        ['🔄 تحويل بين الحسابات', '📊 عرض الحسابات'], 
        ['📈 عرض المصروفات', '🏦 إضافة حساب جديد'],
        ['📋 كشف حساب', '📨 معالجة رسالة بنك']
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

@allowed_user_only
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

@allowed_user_only
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

@allowed_user_only
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

@allowed_user_only
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

@allowed_user_only
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

@allowed_user_only
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

@allowed_user_only
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
        update.message.reply_text(
            f"✅ تم تسجيل دخل {amount} ريال إلى {account_name} من {source}\n"
            f"📊 الرصيد الحالي: {new_balance:,.1f} ريال"
        )
    except ValueError:
        update.message.reply_text("❌ المبلغ يجب أن يكون رقماً!")
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
    
    return ConversationHandler.END

@allowed_user_only
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

@allowed_user_only
def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("❌ تم الإلغاء.")
    return ConversationHandler.END

@allowed_user_only
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
    elif text == '📨 معالجة رسالة بنك':
        process_bank_message(update, context)
    else:
        update.message.reply_text("👋 استخدم الأزرار في لوحة المفاتيح للتفاعل مع البوت")

@allowed_user_only
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

@allowed_user_only
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

@allowed_user_only
def account_statement(update: Update, context: CallbackContext):
    accounts, _, _ = load_data()
    
    accounts_list = get_accounts_without_emoji(accounts)
    
    update.message.reply_text(
        "📋 **كشف حساب:**\n\n"
        "أدخل اسم الحساب الذي تريد كشف حسابه:\n\n"
        f"🏦 **الحسابات المتاحة:**\n{accounts_list}",
        parse_mode='Markdown'
    )
    return CATEGORY

from telegram.utils.helpers import escape_markdown
from telegram.error import BadRequest

@allowed_user_only
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
                    # هروب النص لتجنب مشاكل Markdown
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

# دالة جديدة لمعالجة رسائل البنك
@allowed_user_only
def process_bank_message(update: Update, context: CallbackContext):
    update.message.reply_text(
        "📨 **معالجة رسالة البنك:**\n\n"
        "📋 الرجاء لصق رسالة البنك التي تحتوي على المبلغ:\n\n"
        "📌 سأقوم باستخراج المبلغ تلقائياً وعرضه لك.",
        parse_mode='Markdown',
        reply_markup=ReplyKeyboardRemove()
    )
    return BANK_MESSAGE

@allowed_user_only
def handle_bank_message(update: Update, context: CallbackContext):
    try:
        # إذا كان هناك رسالة بنك محفوظة مسبقاً (يعني المستخدم يدخل مبلغ يدوي)
        if 'bank_message' in context.user_data:
            try:
                amount = float(update.message.text)
                context.user_data['extracted_amount'] = amount
                
                # تنظيف الرسالة القديمة
                context.user_data.pop('bank_message', None)
                
                # عرض أزرار الخيارات
                keyboard = [
                    ['💸 إضافة كدخل', '➕ إضافة كمصروف'],
                    ['🔄 إضافة كتحويل', '❌ إلغاء']
                ]
                reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
                
                update.message.reply_text(
                    f"✅ تم حفظ المبلغ: *{amount:,.2f} ريال*\n\n"
                    "📋 اختر نوع المعاملة:",
                    parse_mode='Markdown',
                    reply_markup=reply_markup
                )
                
                return BANK_MESSAGE
                
            except ValueError:
                update.message.reply_text("❌ المبلغ يجب أن يكون رقماً! الرجاء المحاولة مرة أخرى:")
                return BANK_MESSAGE
        
        # إذا كانت رسالة بنك جديدة
        bank_message = update.message.text
        amount = extract_amount_from_bank_message(bank_message)
        
        if amount is None:
            update.message.reply_text(
                "❌ لم أستطع العثور على مبلغ في الرسالة.\n\n"
                "📋 الرجاء إدخال المبلغ يدوياً:"
            )
            context.user_data['bank_message'] = bank_message
            return BANK_MESSAGE
        
        # حفظ البيانات
        context.user_data['extracted_amount'] = amount
        context.user_data['bank_message'] = bank_message
        
        # عرض أزرار الخيارات
        keyboard = [
            ['💸 إضافة كدخل', '➕ إضافة كمصروف'],
            ['🔄 إضافة كتحويل', '❌ إلغاء']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        update.message.reply_text(
            f"✅ تم استخراج المبلغ: *{amount:,.2f} ريال*\n\n"
            "📋 اختر نوع المعاملة:",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        return BANK_MESSAGE
        
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
        return ConversationHandler.END


@allowed_user_only
def handle_bank_transaction_type(update: Update, context: CallbackContext):
    try:
        transaction_type_btn = update.message.text
        amount = context.user_data.get('extracted_amount')
        
        if not amount:
            update.message.reply_text("❌ لم يتم تحديد مبلغ. الرجاء البدء من جديد.")
            return ConversationHandler.END
        
        if transaction_type_btn == '❌ إلغاء':
            update.message.reply_text("❌ تم إلغاء العملية.")
            context.user_data.clear()
            return ConversationHandler.END
        
        elif transaction_type_btn == '💸 إضافة كدخل':
            context.user_data['transaction_type'] = 'دخل'
            update.message.reply_text(
                f"💰 إضافة دخل بقيمة: *{amount:,.2f} ريال*\n\n"
                "📋 أدخل اسم الحساب أو جزء منه:",
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardRemove()
            )
            return ACCOUNT_NAME
            
        elif transaction_type_btn == '➕ إضافة كمصروف':
            context.user_data['transaction_type'] = 'مصروف'
            update.message.reply_text(
                f"💸 إضافة مصروف بقيمة: *{amount:,.2f} ريال*\n\n"
                "📋 أدخل اسم الحساب أو جزء منه:",
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardRemove()
            )
            return ACCOUNT_NAME
            
        elif transaction_type_btn == '🔄 إضافة كتحويل':
            context.user_data['transaction_type'] = 'تحويل'
            update.message.reply_text(
                f"🔄 تحويل بقيمة: *{amount:,.2f} ريال*\n\n"
                "📋 أدخل اسم الحساب المصدر أو جزء منه:",
                parse_mode='Markdown',
                reply_markup=ReplyKeyboardRemove()
            )
            return ACCOUNT_NAME
            
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
        return ConversationHandler.END

@allowed_user_only
def handle_account_name(update: Update, context: CallbackContext):
    try:
        account_input = update.message.text.strip()
        
        accounts, _, _ = load_data()
        
        # البحث عن اسم الحساب
        account_name = get_account_name(account_input, accounts)
        
        if not account_name:
            # عرض الحسابات المتاحة للمساعدة
            accounts_list = get_accounts_without_emoji(accounts)
            update.message.reply_text(
                f"❌ الحساب '{account_input}' غير موجود!\n\n"
                f"🏦 **الحسابات المتاحة:**\n{accounts_list}\n\n"
                "📋 الرجاء إدخال اسم الحساب مرة أخرى:",
                parse_mode='Markdown'
            )
            return ACCOUNT_NAME
        
        transaction_type = context.user_data.get('transaction_type')
        amount = context.user_data.get('extracted_amount')
        
        if transaction_type in ['دخل', 'مصروف']:
            context.user_data['account_name'] = account_name
            
            # تنظيف اسم الحساب للعرض
            account_clean = re.sub(r'[^\w\s]', '', account_name).strip()
            
            update.message.reply_text(
                f"📋 أدخل التصنيف لـ {transaction_type} بقيمة {amount:,.2f} ريال في حساب {account_clean}:\n\n"
                "💡 يمكنك كتابة 'تخطي' لاستخدام التصنيف التلقائي",
                reply_markup=ReplyKeyboardRemove()
            )
            return CATEGORY
            
        elif transaction_type == 'تحويل':
            context.user_data['from_account'] = account_name
            account_clean = re.sub(r'[^\w\s]', '', account_name).strip()
            
            update.message.reply_text(
                f"🔄 تحويل من: {account_clean}\n\n"
                "📋 أدخل اسم الحساب الهدف أو جزء منه:",
                reply_markup=ReplyKeyboardRemove()
            )
            return TRANSFER_TO_ACCOUNT
            
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END@allowed_user_only
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
        
        # الحصول على الأرصدة الحالية
        from_balance_before = accounts.at[from_index[0], 'الرصيد']
        to_index = accounts[accounts['اسم الحساب'] == to_acc].index
        to_balance_before = accounts.at[to_index[0], 'الرصيد']
        
        # إجراء التحويل
        accounts.at[from_index[0], 'الرصيد'] -= amount
        accounts.at[to_index[0], 'الرصيد'] += amount
        
        # الحصول على الأرصدة الجديدة
        from_balance_after = accounts.at[from_index[0], 'الرصيد']
        to_balance_after = accounts.at[to_index[0], 'الرصيد']
        
        # تسجيل التحويل
        new_transfer = {
            'التاريخ': datetime.now().strftime('%Y-%m-%d'),
            'من حساب': from_acc,
            'إلى حساب': to_acc,
            'المبلغ': amount
        }
        transfers = pd.concat([transfers, pd.DataFrame([new_transfer])], ignore_index=True)
        
        save_data(accounts, transactions, transfers)
        
        # تنظيف أسماء الحسابات من الإيموجي للعرض
        from_acc_clean = re.sub(r'[^\w\s]', '', from_acc).strip()
        to_acc_clean = re.sub(r'[^\w\s]', '', to_acc).strip()
        
        update.message.reply_text(
            f"✅ تم تحويل {amount:,.0f} ريال من {from_acc_clean} إلى {to_acc_clean}\n\n"
            f"💵 الرصيد الجديد في {from_acc_clean}: {from_balance_after:,.0f} ريال\n"
            f"💵 الرصيد الجديد في {to_acc_clean}: {to_balance_after:,.0f} ريال"
        )
    except ValueError:
        update.message.reply_text("❌ المبلغ يجب أن يكون رقماً!")
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
    
    return ConversationHandler.END

@allowed_user_only
def handle_category(update: Update, context: CallbackContext):
    try:
        user_input = update.message.text.strip()
        
        # إذا كتب المستخدم "تخطي" أو تركها فارغة، نستخلص التصنيف تلقائياً
        if user_input.lower() in ['تخطي', 'skip', ''] and 'bank_message' in context.user_data:
            category = extract_category_from_bank_message(context.user_data['bank_message'])
        else:
            category = user_input
        
        # إذا لم يتم تحديد تصنيف، نستخدم افتراضي
        if not category:
            transaction_type = context.user_data.get('transaction_type', 'مصروف')
            category = "مصروف عام" if transaction_type == 'مصروف' else "دخل عام"
        
        # التحقق من وجود البيانات المطلوبة
        required_data = ['transaction_type', 'extracted_amount', 'account_name']
        if not all(key in context.user_data for key in required_data):
            update.message.reply_text("❌ حدث خطأ في العملية. الرجاء البدء من جديد.")
            context.user_data.clear()
            return ConversationHandler.END
        
        transaction_type = context.user_data['transaction_type']
        amount = context.user_data['extracted_amount']
        account_name = context.user_data['account_name']
        
        accounts, transactions, transfers = load_data()
        
        # التحقق من أن الحساب لا يزال موجوداً
        if account_name not in accounts['اسم الحساب'].values:
            update.message.reply_text("❌ الحساب لم يعد موجوداً! الرجاء البدء من جديد.")
            context.user_data.clear()
            return ConversationHandler.END
        
        if transaction_type == 'دخل':
            # تحديث رصيد الحساب
            account_index = accounts[accounts['اسم الحساب'] == account_name].index
            accounts.at[account_index[0], 'الرصيد'] += amount
            new_balance = accounts.at[account_index[0], 'الرصيد']
            
            # إضافة المعاملة
            new_transaction = {
                'التاريخ': datetime.now().strftime('%Y-%m-%d'),
                'النوع': 'دخل',
                'المبلغ': amount,
                'الحساب': account_name,
                'التصنيف': category
            }
            transactions = pd.concat([transactions, pd.DataFrame([new_transaction])], ignore_index=True)
            
            save_data(accounts, transactions, transfers)
            
            # تنظيف اسم الحساب من الإيموجي للعرض
            account_clean = re.sub(r'[^\w\s]', '', account_name).strip()
            
            update.message.reply_text(
                f"✅ تم تسجيل دخل {amount:,.2f} ريال إلى {account_clean} للتصنيف {category}\n"
                f"📊 الرصيد الحالي: {new_balance:,.0f} ريال"
            )
            
        elif transaction_type == 'مصروف':
            # تحديث رصيد الحساب
            account_index = accounts[accounts['اسم الحساب'] == account_name].index
            accounts.at[account_index[0], 'الرصيد'] -= amount
            new_balance = accounts.at[account_index[0], 'الرصيد']
            
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
            
            # تنظيف اسم الحساب من الإيموجي للعرض
            account_clean = re.sub(r'[^\w\s]', '', account_name).strip()
            
            update.message.reply_text(
                f"✅ تم تسجيل مصروف {amount:,.2f} ريال من {account_clean} للتصنيف {category}\n"
                f"📊 الرصيد الحالي: {new_balance:,.0f} ريال"
            )
        
        # تنظيف بيانات المستخدم
        context.user_data.clear()
        
        return ConversationHandler.END
        
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
        context.user_data.clear()
        return ConversationHandler.END
#  دالة لاستخلاص التصنيف من رسالة البنك
def extract_category_from_bank_message(message):
    """
    استخلاص التصنيف من رسالة البنك تلقائياً
    """
    message_lower = message.lower()
    
    # أنماط للتعرف على التصنيف من الرسالة
    patterns = {
        'مطعم': ['restaurant', 'مطعم', 'كافيه', 'cafe', 'coffee', 'ماكدونالدز', 'kfc', 'برجر'],
        'سوبرماركت': ['supermarket', 'سوبرماركت', 'هايبر', 'hyper', 'دانوب', 'danube', 'كارفور', 'carrefour'],
        'وقود': ['fuel', 'بنزين', 'وقود', 'gas', 'petrol', 'محطة', 'station'],
        'مواصلات': ['transport', 'مواصلات', 'تاكسي', 'taxi', 'اوبر', 'uber'],
        'تسوق': ['shopping', 'تسوق', 'ملابس', 'clothes', 'ماركة', 'brand'],
        'فواتير': ['bill', 'فاتورة', 'كهرباء', 'water', 'ماء', 'electricity'],
        'صحة': ['medical', 'صحة', 'دواء', 'hospital', 'مستشفى', 'صيدلية'],
        'ترفيه': ['entertainment', 'ترفيه', 'سينما', 'cinema', 'حديقة', 'park'],
        'تعليم': ['education', 'تعليم', 'كتاب', 'school', 'مدرسة', 'جامعة'],
        'أونلاين': ['online', 'إنترنت', 'internet', 'apple', 'google', 'paypal', 'purchase']
    }
    
    # البحث عن الأنماط في الرسالة
    for category, keywords in patterns.items():
        for keyword in keywords:
            if keyword in message_lower:
                return category
    
    # البحث عن كلمات محددة في الرسالة
    if any(word in message_lower for word in ['purchase', 'شراء', 'عملية']):
        return 'شراء'
    if any(word in message_lower for word in ['danube', 'fo']):
        return 'سوبرماركت'
    
    return 'مصروف عام'


#  دالة جديدة لمعالجة الأزرار بشكل صحيح:
@allowed_user_only
def handle_bank_transaction_type(update: Update, context: CallbackContext):
    try:
        transaction_type = update.message.text
        amount = context.user_data.get('extracted_amount')
        
        if not amount:
            # إذا لم يتم استخراج المبلغ، اطلبه يدوياً
            update.message.reply_text("📋 الرجاء إدخال المبلغ:")
            return BANK_MESSAGE
        
        if transaction_type == '❌ إلغاء':
            update.message.reply_text("❌ تم إلغاء العملية.")
            # تنظيف بيانات المستخدم
            context.user_data.pop('extracted_amount', None)
            context.user_data.pop('bank_message', None)
            return ConversationHandler.END
        
        elif transaction_type == '💸 إضافة كدخل':
            context.user_data['transaction_type'] = 'دخل'
            update.message.reply_text(
                f"💰 إضافة دخل بقيمة: *{amount:,.2f} ريال*\n\n"
                "📋 أدخل اسم الحساب أو جزء منه:",
                parse_mode='Markdown'
            )
            return ACCOUNT_NAME
            
        elif transaction_type == '➕ إضافة كمصروف':
            context.user_data['transaction_type'] = 'مصروف'
            update.message.reply_text(
                f"💸 إضافة مصروف بقيمة: *{amount:,.2f} ريال*\n\n"
                "📋 أدخل اسم الحساب أو جزء منه:",
                parse_mode='Markdown'
            )
            return ACCOUNT_NAME
            
        elif transaction_type == '🔄 إضافة كتحويل':
            context.user_data['transaction_type'] = 'تحويل'
            update.message.reply_text(
                f"🔄 تحويل بقيمة: *{amount:,.2f} ريال*\n\n"
                "📋 أدخل اسم الحساب المصدر أو جزء منه:",
                parse_mode='Markdown'
            )
            return ACCOUNT_NAME
            
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
        return ConversationHandler.END

@allowed_user_only
def handle_transfer_to_account(update: Update, context: CallbackContext):
    try:
        account_input = update.message.text.strip()
        accounts, _, _ = load_data()
        
        # البحث عن اسم الحساب
        account_name = get_account_name(account_input, accounts)
        if not account_name:
            # عرض الحسابات المتاحة للمساعدة
            accounts_list = get_accounts_without_emoji(accounts)
            update.message.reply_text(
                f"❌ الحساب غير موجود!\n\n"
                f"🏦 **الحسابات المتاحة:**\n{accounts_list}\n\n"
                "📋 الرجاء إدخال اسم الحساب مرة أخرى:",
                parse_mode='Markdown'
            )
            return TRANSFER_TO_ACCOUNT
        
        # التحقق من أن الحساب الهدف مختلف عن المصدر
        from_account = context.user_data.get('from_account')
        if account_name == from_account:
            update.message.reply_text("❌ لا يمكن التحويل لنفس الحساب! الرجاء اختيار حساب مختلف:")
            return TRANSFER_TO_ACCOUNT
        
        amount = context.user_data.get('extracted_amount')
        
        # تنفيذ التحويل
        accounts, transactions, transfers = load_data()
        
        # التحقق من الرصيد الكافي
        from_index = accounts[accounts['اسم الحساب'] == from_account].index
        if accounts.at[from_index[0], 'الرصيد'] < amount:
            update.message.reply_text("❌ الرصيد غير كافي!")
            return ConversationHandler.END
        
        # الحصول على الأرصدة الحالية
        from_balance_before = accounts.at[from_index[0], 'الرصيد']
        to_index = accounts[accounts['اسم الحساب'] == account_name].index
        to_balance_before = accounts.at[to_index[0], 'الرصيد']
        
        # إجراء التحويل
        accounts.at[from_index[0], 'الرصيد'] -= amount
        accounts.at[to_index[0], 'الرصيد'] += amount
        
        # الحصول على الأرصدة الجديدة
        from_balance_after = accounts.at[from_index[0], 'الرصيد']
        to_balance_after = accounts.at[to_index[0], 'الرصيد']
        
        # تسجيل التحويل
        new_transfer = {
            'التاريخ': datetime.now().strftime('%Y-%m-%d'),
            'من حساب': from_account,
            'إلى حساب': account_name,
            'المبلغ': amount
        }
        transfers = pd.concat([transfers, pd.DataFrame([new_transfer])], ignore_index=True)
        
        save_data(accounts, transactions, transfers)
        
        # تنظيف أسماء الحسابات من الإيموجي للعرض
        from_account_clean = re.sub(r'[^\w\s]', '', from_account).strip()
        to_account_clean = re.sub(r'[^\w\s]', '', account_name).strip()
        
        update.message.reply_text(
            f"✅ تم تحويل {amount:,.2f} ريال من {from_account_clean} إلى {to_account_clean}\n\n"
            f"💵 الرصيد الجديد في {from_account_clean}: {from_balance_after:,.0f} ريال\n"
            f"💵 الرصيد الجديد في {to_account_clean}: {to_balance_after:,.0f} ريال"
        )
        
        # تنظيف بيانات المستخدم
        context.user_data.pop('extracted_amount', None)
        context.user_data.pop('transaction_type', None)
        context.user_data.pop('from_account', None)
        
        return ConversationHandler.END
        
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
        # تنظيف بيانات المستخدم في حالة الخطأ
        context.user_data.pop('extracted_amount', None)
        context.user_data.pop('transaction_type', None)
        context.user_data.pop('from_account', None)
        return ConversationHandler.END


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
            MessageHandler(Filters.regex('^📨 معالجة رسالة بنك$'), process_bank_message)
        ],
        states={
            ADD_EXPENSE: [MessageHandler(Filters.text & ~Filters.command, handle_add_expense)],
            ADD_INCOME: [MessageHandler(Filters.text & ~Filters.command, handle_add_income)],
            TRANSFER: [MessageHandler(Filters.text & ~Filters.command, handle_transfer)],
            NEW_ACCOUNT: [MessageHandler(Filters.text & ~Filters.command, handle_new_account)],
            CATEGORY: [MessageHandler(Filters.text & ~Filters.command, handle_account_statement)],
            BANK_MESSAGE: [
                MessageHandler(Filters.regex('^(💸 إضافة كدخل|➕ إضافة كمصروف|🔄 إضافة كتحويل|❌ إلغاء)$'), handle_bank_transaction_type),
                MessageHandler(Filters.text & ~Filters.command, handle_bank_message)
            ],
            ACCOUNT_NAME: [MessageHandler(Filters.text & ~Filters.command, handle_account_name)],
            TRANSFER_TO_ACCOUNT: [MessageHandler(Filters.text & ~Filters.command, handle_transfer_to_account)]
        },
        fallbacks=[CommandHandler('start', start), CommandHandler('cancel', cancel)]
    )
    
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    
    print("🤖 البوت يعمل...")
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()