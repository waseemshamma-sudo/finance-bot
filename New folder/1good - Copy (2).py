import os
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from dotenv import load_dotenv
from datetime import datetime
import re
from functools import wraps

# تحميل المتغيرات من ملف .env
load_dotenv(r"C:\Users\Admin\finance\.env")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("❌ لم يتم العثور على TELEGRAM_BOT_TOKEN في ملف البيئة")

# المعرف المسموح له باستخدام البوت
ALLOWED_USER_ID = 1919573036

# دالة التحقق من صلاحية المستخدم
def restricted(func):
    @wraps(func)
    def wrapped(update: Update, context: CallbackContext, *args, **kwargs):
        user_id = update.effective_user.id
        if user_id != ALLOWED_USER_ID:
            update.message.reply_text("⚠️ غير مصرح لك باستخدام هذا البوت")
            return ConversationHandler.END
        return func(update, context, *args, **kwargs)
    return wrapped

# حالات المحادثة
ADD_EXPENSE, ADD_INCOME, TRANSFER, NEW_ACCOUNT, CATEGORY = range(5)
AMOUNT_EXTRACTION, SELECT_ACTION, SELECT_ACCOUNT_FOR_EXPENSE, SELECT_ACCOUNT_FOR_INCOME, SELECT_FROM_ACCOUNT, SELECT_TO_ACCOUNT = range(6, 12)
TRANSFER_CONFIRM = 12

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

# أوامر البوت
@restricted 
def start(update: Update, context: CallbackContext):
    keyboard = [
        ['➕ إضافة مصروف', '💸 إضافة دخل'], 
        ['🔄 تحويل بين الحسابات', '📊 عرض الحسابات'], 
        ['📈 عرض المصروفات', '🏦 إضافة حساب جديد'],
        ['📋 كشف حساب', '/Start']
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
    
    recent_transactions = transactions.tail(5)
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
        "• `طعام, 50, النقدي`\n"
        "• `مواصلات, 30, البنك الأهلي`",
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
        "• `راتب, 5000, البنك الأهلي`\n"
        "• `عمل حر, 300, النقدي`",
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
        "`البنك الأهلي, النقدي, 1000`",
        parse_mode='Markdown'
    )
    return TRANSFER

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
        update.message.reply_text(
            f"✅ تم تسجيل دخل {amount} ريال إلى {account_name} من {source}\n"
            f"📊 الرصيد الحالي: {new_balance:,.1f} ريال"
        )
    except ValueError:
        update.message.reply_text("❌ المبلغ يجب أن يكون رقماً!")
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
    
    return ConversationHandler.END

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
        
        # البحث عن أسماء الحسابات باستخدام الدالة الجديدة
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

# دالة تنفيذ التحويل
@restricted 
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
@restricted 
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

@restricted 
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

@restricted 
def handle_account_statement(update: Update, context: CallbackContext):
    try:
        account_input = update.message.text.strip()
        
        # معالجة زر الرجوع
        if account_input == '↩️ رجوع للقائمة الرئيسية':
            return start(update, context)
        
        accounts, transactions, transfers = load_data()
        
        # البحث عن اسم الحساب
        account_name = get_account_name(account_input, accounts)
        if not account_name:
            update.message.reply_text("❌ الحساب غير موجود!")
            return account_statement(update, context)
        
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
        def safe_sum(series):
            result = series.sum()
            return result if not pd.isna(result) else 0
        
        total_income = safe_sum(account_transactions[account_transactions['النوع'] == 'دخل']['المبلغ'])
        total_expenses = safe_sum(account_transactions[account_transactions['النوع'] == 'مصروف']['المبلغ'])
        total_incoming_transfers = safe_sum(incoming_transfers['المبلغ'])
        total_outgoing_transfers = safe_sum(outgoing_transfers['المبلغ'])
        
        opening_balance = current_balance + total_expenses - total_income + total_outgoing_transfers - total_incoming_transfers
        
        # إنشاء تقرير منظم بدون تنسيق Markdown
        message = f"📊 كشف حساب: {cleaned_account_name}\n"
        message += f"📋 النوع: {account_type}\n"
        message += f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d')}\n"
        message += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        
        message += f"💰 الرصيد الافتتاحي: {opening_balance:,.0f} ريال\n\n"
        
        # المعاملات
        message += "💳 المعاملات\n"
        message += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        
        if account_transactions.empty:
            message += "لا توجد معاملات\n\n"
        else:
            # الدخل
            income_transactions = account_transactions[account_transactions['النوع'] == 'دخل']
            if not income_transactions.empty:
                message += "↙️ الدخل:\n"
                for _, transaction in income_transactions.iterrows():
                    message += f"   + {transaction['المبلغ']:,.0f} ريال - {transaction['التصنيف']} ({transaction['التاريخ']})\n"
                income_sum = safe_sum(income_transactions['المبلغ'])
                message += f"   المجموع: +{income_sum:,.0f} ريال\n\n"
            
            # المصروفات
            expense_transactions = account_transactions[account_transactions['النوع'] == 'مصروف']
            if not expense_transactions.empty:
                message += "↗️ المصروفات:\n"
                for _, transaction in expense_transactions.iterrows():
                    message += f"   - {transaction['المبلغ']:,.0f} ريال - {transaction['التصنيف']} ({transaction['التاريخ']})\n"
                expense_sum = safe_sum(expense_transactions['المبلغ'])
                message += f"   المجموع: -{expense_sum:,.0f} ريال\n\n"
        
        # التحويلات
        message += "🔄 التحويلات\n"
        message += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        
        if outgoing_transfers.empty and incoming_transfers.empty:
            message += "لا توجد تحويلات\n\n"
        else:
            # التحويلات الواردة
            if not incoming_transfers.empty:
                message += "⬅️ التحويلات الواردة:\n"
                for _, transfer in incoming_transfers.iterrows():
                    from_acc_clean = re.sub(r'[^\w\s]', '', transfer['من حساب']).strip()
                    message += f"   + {transfer['المبلغ']:,.0f} ريال من {from_acc_clean} ({transfer['التاريخ']})\n"
                incoming_sum = safe_sum(incoming_transfers['المبلغ'])
                message += f"   المجموع: +{incoming_sum:,.0f} ريال\n\n"
            
            # التحويلات الصادرة
            if not outgoing_transfers.empty:
                message += "➡️ التحويلات الصادرة:\n"
                for _, transfer in outgoing_transfers.iterrows():
                    to_acc_clean = re.sub(r'[^\w\s]', '', transfer['إلى حساب']).strip()
                    message += f"   - {transfer['المبلغ']:,.0f} ريال إلى {to_acc_clean} ({transfer['التاريخ']})\n"
                outgoing_sum = safe_sum(outgoing_transfers['المبلغ'])
                message += f"   المجموع: -{outgoing_sum:,.0f} ريال\n\n"
        
        # الملخص المالي
        message += "🧮 الملخص المالي\n"
        message += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        message += f"الرصيد الافتتاحي: {opening_balance:,.0f} ريال\n"
        message += f"إجمالي الدخل: +{total_income:,.0f} ريال\n"
        message += f"إجمالي المصروفات: -{total_expenses:,.0f} ريال\n"
        message += f"صافي التحويلات: {total_incoming_transfers - total_outgoing_transfers:+,.0f} ريال\n"
        message += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        message += f"💰 الرصيد الختامي: {current_balance:,.0f} ريال"
        
        # إرسال الرسالة بدون تنسيق Markdown
        update.message.reply_text(message)
        
        return ConversationHandler.END
        
    except Exception as e:
        update.message.reply_text(f"❌ خطأ: {str(e)}")
        return ConversationHandler.END




# دالة جديدة لاستخلاص المبلغ من النص
@restricted
def extract_amount_from_text(update: Update, context: CallbackContext):
    text = update.message.text
    amount = None
    description = "معاملة غير معروفة"
    
    # أنماط مختلفة لاستخلاص المبلغ
    patterns = [
        r'Amount\s+([\d,]+\.?\d*)\s+SAR',  # Amount 67.00 SAR
        r'بـ:([\d,]+\.?\d*)\s+SAR',        # بـ:29.5 SAR
        r'بـ:([\d,]+\.?\d*)\s*SAR',        # بـ:11 SAR (بدون مسافة)
        r'المبلغ:\s*([\d,]+\.?\d*)',       # المبلغ: 100
        r'ريال\s*([\d,]+\.?\d*)',          # ريال 150
        r'SAR\s*([\d,]+\.?\d*)',           # SAR 200
        r'([\d,]+\.?\d*)\s*ريال',          # 150 ريال
        r'([\d,]+\.?\d*)\s*SAR',           # 200 SAR
        r'بـ\s*([\d,]+\.?\d*)',            # بـ 100
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                amount = float(amount_str)
                break
            except ValueError:
                continue
    
    if amount is None:
        # محاولة العثور على أي رقم في النص
        number_matches = re.findall(r'[\d,]+\.?\d*', text)
        if number_matches:
            try:
                amount = float(number_matches[0].replace(',', ''))
            except ValueError:
                pass
    
    if amount is not None:
        # استخلاص وصف المعاملة
        desc_patterns = [
            r'Online Purchase\s+(.+)',          # Online Purchase 
            r'شراء\s+(.+)',                     # شراء ***1127
            r'عبر:(.+)',                        # عبر:*1127
            r'من:(.+)',                         # من:MGAMA ALSHAMEL CORPERT
            r'Authorized by\s+(.+)',            # Authorized by Express Food Company
            r'من:\s*(.+)',                      # من: MTAM AHMD BAAEMAN
        ]
        
        for pattern in desc_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                description = match.group(1).strip()
                if len(description) > 30:
                    description = description[:30] + "..."
                break
        
        # حفظ البيانات مؤقتاً
        context.user_data['extracted_amount'] = amount
        context.user_data['transaction_description'] = description
        context.user_data['original_text'] = text
        
        # عرض خيارات الإجراء
        keyboard = [
            ['💸 تسجيل كمصروف', '💰 تسجيل كدخل'],
            ['🔄 تسجيل كتحويل', '❌ إلغاء']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        update.message.reply_text(
            f"✅ تم استخلاص المبلغ: {amount:.2f} ريال\n"
            f"📝 الوصف: {description}\n\n"
            "اختر الإجراء المناسب:",
            reply_markup=reply_markup
        )
        return SELECT_ACTION
    else:
        update.message.reply_text(
            "❌ لم أتمكن من استخلاص مبلغ من النص.\n\n"
            "📋 تأكد من أن النص يحتوي على مبلغ بشكل واضح مثل:\n"
            "• 'Amount 67.00 SAR'\n"
            "• 'بـ:29.5 SAR'\n"
            "• '100 ريال'\n\n"
            "استخدم الأزرار في لوحة المفاتيح للتفاعل مع البوت."
        )
        return ConversationHandler.END
# معالجة اختيار الإجراء
@restricted
def handle_action_selection(update: Update, context: CallbackContext):
    action = update.message.text
    amount = context.user_data.get('extracted_amount')
    description = context.user_data.get('transaction_description', 'معاملة')
    
    if action == '↩️ رجوع للقائمة الرئيسية':
        return start(update, context)
    elif action == '💸 تسجيل كمصروف':
        return handle_expense_from_extraction(update, context)
    elif action == '💰 تسجيل كدخل':
        return handle_income_from_extraction(update, context)
    elif action == '🔄 تسجيل كتحويل':
        return handle_transfer_from_extraction(update, context)
    elif action == '❌ إلغاء':
        # العودة للقائمة الرئيسية بدلاً من الإلغاء التام
        return start(update, context)
    elif action == '/Start':
        return start(update, context)
    else:
        # إذا كان الخيار غير معروف، إعادة عرض الخيارات
        keyboard = [
            ['💸 تسجيل كمصروف', '💰 تسجيل كدخل'],
            ['🔄 تسجيل كتحويل', '❌ إلغاء'],
            ['↩️ رجوع للقائمة الرئيسية']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        update.message.reply_text(
            f"❌ خيار غير صالح\n\n"
            f"✅ تم استخلاص المبلغ: {amount:.2f} ريال\n"
            f"📝 الوصف: {description}\n\n"
            "اختر الإجراء المناسب:",
            reply_markup=reply_markup
        )
        return SELECT_ACTION

# معالجة المصروف من الاستخلاص
@restricted
def handle_expense_from_extraction(update: Update, context: CallbackContext):
    accounts, _, _ = load_data()
    
    # تصفية الحسابات المناسبة للمصروف (بنوك وبطاقات ائتمان)
    bank_accounts = accounts[accounts['النوع'].isin(['بنك', 'بطاقة ائتمان'])]
    
    if bank_accounts.empty:
        update.message.reply_text("❌ لا توجد حسابات بنكية أو بطاقات ائتمان متاحة!")
        return ConversationHandler.END
    
    # إنشاء لوحة مفاتيح بالحسابات
    keyboard = []
    for _, account in bank_accounts.iterrows():
        account_name = re.sub(r'[^\w\s]', '', account['اسم الحساب']).strip()
        keyboard.append([account_name])
    
    keyboard.append(['❌ إلغاء'])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    amount = context.user_data.get('extracted_amount')
    description = context.user_data.get('transaction_description', 'مصروف')
    
    # إزالة تنسيق Markdown من الرسالة
    update.message.reply_text(
        f"💸 تسجيل مصروف: {amount:.2f} ريال\n"
        f"📝 السبب: {description}\n\n"
        "اختر الحساب المصدر:",
        reply_markup=reply_markup
    )
    
    return SELECT_ACCOUNT_FOR_EXPENSE



# معالجة الدخل من الاستخلاص
@restricted
def handle_income_from_extraction(update: Update, context: CallbackContext):
    if update.message.text == '↩️ رجوع للقائمة الرئيسية':
        return start(update, context)
    
    accounts, _, _ = load_data()
    
    # السماح بجميع أنواع الحسابات للدخل (بنك، نقدي، أشخاص، دين)
    income_accounts = accounts[accounts['النوع'].isin(['بنك', 'نقدي', 'أشخاص', 'دين', 'بطاقة ائتمان'])]
    
    if income_accounts.empty:
        # إذا لم توجد حسابات، عرض القائمة الرئيسية
        keyboard = [
            ['➕ إضافة مصروف', '💸 إضافة دخل'], 
            ['🔄 تحويل بين الحسابات', '📊 عرض الحسابات'], 
            ['📈 عرض المصروفات', '🏦 إضافة حساب جديد'],
            ['📋 كشف حساب']
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        update.message.reply_text(
            "❌ لا توجد حسابات مناسبة لإضافة الدخل!\n\n"
            "✅ يمكنك إضافة حساب جديد من القائمة الرئيسية:",
            reply_markup=reply_markup
        )
        return ConversationHandler.END
    
    # إنشاء لوحة مفاتيح بالحسابات
    keyboard = []
    for _, account in income_accounts.iterrows():
        account_name = re.sub(r'[^\w\s]', '', account['اسم الحساب']).strip()
        keyboard.append([account_name])
    
    keyboard.append(['↩️ رجوع للقائمة الرئيسية', '❌ إلغاء'])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    amount = context.user_data.get('extracted_amount')
    description = context.user_data.get('transaction_description', 'دخل')
    
    update.message.reply_text(
        f"💰 تسجيل دخل: {amount:.2f} ريال\n"
        f"📝 المصدر: {description}\n\n"
        "اختر الحساب المستهدف:",
        reply_markup=reply_markup
    )
    
    return SELECT_ACCOUNT_FOR_INCOME
@restricted
def handle_income_account_selection(update: Update, context: CallbackContext):
    if update.message.text == '↩️ رجوع للقائمة الرئيسية':
        return start(update, context)
    if update.message.text == '❌ إلغاء':
        update.message.reply_text("❌ تم الإلغاء.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    account_input = update.message.text.strip()
    amount = context.user_data.get('extracted_amount')
    description = context.user_data.get('transaction_description', 'دخل')
    
    accounts, transactions, transfers = load_data()
    
    # البحث عن اسم الحساب
    account_name = get_account_name(account_input, accounts)
    if not account_name:
        update.message.reply_text("❌ الحساب غير موجود!")
        return ConversationHandler.END
    
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
        'التصنيف': description
    }
    transactions = pd.concat([transactions, pd.DataFrame([new_transaction])], ignore_index=True)
    
    save_data(accounts, transactions, transfers)
    
    update.message.reply_text(
        f"✅ تم تسجيل دخل {amount:.2f} ريال إلى {account_name}\n"
        f"📝 المصدر: {description}\n"
        f"📊 الرصيد الجديد: {new_balance:,.2f} ريال",
        reply_markup=ReplyKeyboardRemove()
    )
    
    return start(update, context)

# معالجة التحويل من الاستخلاص
@restricted
def handle_transfer_from_extraction(update: Update, context: CallbackContext):
    accounts, _, _ = load_data()
    
    # إنشاء لوحة مفاتيح بجميع الحسابات
    keyboard = []
    for _, account in accounts.iterrows():
        account_name = re.sub(r'[^\w\s]', '', account['اسم الحساب']).strip()
        keyboard.append([account_name])
    
    keyboard.append(['❌ إلغاء'])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    amount = context.user_data.get('extracted_amount')
    
    update.message.reply_text(
        f"🔄 **تسجيل تحويل:** {amount:.2f} ريال\n\n"
        "اختر الحساب المصدر:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    
    return SELECT_FROM_ACCOUNT

@restricted
def handle_from_account_selection(update: Update, context: CallbackContext):
    if update.message.text == '↩️ رجوع للقائمة الرئيسية':
        return start(update, context)
    if update.message.text == '❌ إلغاء':
        update.message.reply_text("❌ تم الإلغاء.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    context.user_data['from_account_input'] = update.message.text.strip()
    
    accounts, _, _ = load_data()
    
    # إنشاء لوحة مفاتيح بجميع الحسابات عدا المصدر
    keyboard = []
    for _, account in accounts.iterrows():
        account_name = re.sub(r'[^\w\s]', '', account['اسم الحساب']).strip()
        if account_name != context.user_data['from_account_input']:
            keyboard.append([account_name])
    
    keyboard.append(['❌ إلغاء'])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    update.message.reply_text(
        "اختر الحساب المستلم:",
        reply_markup=reply_markup
    )
    
    return SELECT_TO_ACCOUNT

@restricted
def handle_to_account_selection(update: Update, context: CallbackContext):
    if update.message.text == '↩️ رجوع للقائمة الرئيسية':
        return start(update, context)
    if update.message.text == '❌ إلغاء':
        update.message.reply_text("❌ تم الإلغاء.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    from_acc_input = context.user_data['from_account_input']
    to_acc_input = update.message.text.strip()
    amount = context.user_data.get('extracted_amount')
    
    accounts, transactions, transfers = load_data()
    
    # البحث عن أسماء الحسابات
    from_acc = get_account_name(from_acc_input, accounts)
    to_acc = get_account_name(to_acc_input, accounts)
    
    if not from_acc or not to_acc:
        update.message.reply_text("❌ أحد الحسابات غير موجود!")
        return ConversationHandler.END
    
    if from_acc == to_acc:
        update.message.reply_text("❌ لا يمكن التحويل لنفس الحساب!")
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
        return TRANSFER_CONFIRM
    
    # إذا كان الرصيد كافي، تنفيذ التحويل مباشرة
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
    
    from_balance = accounts.at[from_index[0], 'الرصيد']
    to_balance = accounts.at[to_index[0], 'الرصيد']
    
    update.message.reply_text(
        f"✅ تم تحويل {amount:.2f} ريال من {from_acc} إلى {to_acc}\n\n"
        f"💵 الرصيد الجديد في {from_acc}: {from_balance:,.2f} ريال\n"
        f"💵 الرصيد الجديد في {to_acc}: {to_balance:,.2f} ريال",  # تصحيح الحرف هنا
        reply_markup=ReplyKeyboardRemove()
    )
    
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
    elif text == '/Start':
        start(update, context)
    else:
        update.message.reply_text("👋 استخدم الأزرار في لوحة المفاتيح للتفاعل مع البوت")

# معالجة اختيار الحساب للمصروف
@restricted
def handle_expense_account_selection(update: Update, context: CallbackContext):
    if update.message.text == '↩️ رجوع للقائمة الرئيسية':
        return start(update, context)
    if update.message.text == '❌ إلغاء':
        update.message.reply_text("❌ تم الإلغاء.", reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END
    
    account_input = update.message.text.strip()
    amount = context.user_data.get('extracted_amount')
    description = context.user_data.get('transaction_description', 'مصروف')
    
    accounts, transactions, transfers = load_data()
    
    # البحث عن اسم الحساب
    account_name = get_account_name(account_input, accounts)
    if not account_name:
        update.message.reply_text("❌ الحساب غير موجود!")
        return ConversationHandler.END
    
    # التحقق من نوع الحساب
    account_info = accounts[accounts['اسم الحساب'] == account_name].iloc[0]
    if account_info['النوع'] not in ['بنك', 'بطاقة ائتمان']:
        update.message.reply_text("❌ يمكن سحب المصروفات من الحسابات البنكية أو بطاقات الائتمان فقط!")
        return ConversationHandler.END
    
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
        'التصنيف': description
    }
    transactions = pd.concat([transactions, pd.DataFrame([new_transaction])], ignore_index=True)
    
    save_data(accounts, transactions, transfers)
    
    update.message.reply_text(
        f"✅ تم تسجيل مصروف {amount:.2f} ريال من {account_name}\n"
        f"📝 السبب: {description}\n"
        f"📊 الرصيد الجديد: {new_balance:,.2f} ريال",
        reply_markup=ReplyKeyboardRemove()
    )
    
    # العودة إلى القائمة الرئيسية بعد اكتمال العملية
    return start(update, context)

def main():
    try:
        print("🤖 جاري تهيئة ملف Excel...")
        init_excel_file()
        
        print("🔑 جاري تحميل التوكن...")
        if not TELEGRAM_BOT_TOKEN:
            print("❌ خطأ: لم يتم العثور على TELEGRAM_BOT_TOKEN")
            return
            
        print(f"✅ التوكن محمل: {TELEGRAM_BOT_TOKEN[:10]}...")
        
        print("🚀 جاري تشغيل البوت...")
        updater = Updater(TELEGRAM_BOT_TOKEN)
        dispatcher = updater.dispatcher
        
        print("📋 جاري إعداد معالج المحادثة...")
        conv_handler = ConversationHandler(
            entry_points=[
                MessageHandler(Filters.regex('^➕ إضافة مصروف$'), add_expense),
                MessageHandler(Filters.regex('^💸 إضافة دخل$'), add_income),
                MessageHandler(Filters.regex('^🔄 تحويل بين الحسابات$'), transfer_money),
                MessageHandler(Filters.regex('^🏦 إضافة حساب جديد$'), add_new_account),
                MessageHandler(Filters.regex('^📋 كشف حساب$'), account_statement),
                MessageHandler(Filters.text & ~Filters.command, extract_amount_from_text)
            ],
            states={
                ADD_EXPENSE: [MessageHandler(Filters.text & ~Filters.command, handle_add_expense)],
                ADD_INCOME: [MessageHandler(Filters.text & ~Filters.command, handle_add_income)],
                TRANSFER: [MessageHandler(Filters.text & ~Filters.command, handle_transfer)],
                TRANSFER_CONFIRM: [MessageHandler(Filters.text & ~Filters.command, handle_transfer_confirm)],
                NEW_ACCOUNT: [MessageHandler(Filters.text & ~Filters.command, handle_new_account)],
                CATEGORY: [MessageHandler(Filters.text & ~Filters.command, handle_account_statement)],
                # الحالات الجديدة للاستخلاص
                SELECT_ACTION: [MessageHandler(Filters.text & ~Filters.command, handle_action_selection)],
                SELECT_ACCOUNT_FOR_EXPENSE: [MessageHandler(Filters.text & ~Filters.command, handle_expense_account_selection)],
                SELECT_ACCOUNT_FOR_INCOME: [MessageHandler(Filters.text & ~Filters.command, handle_income_account_selection)],
                SELECT_FROM_ACCOUNT: [MessageHandler(Filters.text & ~Filters.command, handle_from_account_selection)],
                SELECT_TO_ACCOUNT: [MessageHandler(Filters.text & ~Filters.command, handle_to_account_selection)],
            },
            fallbacks=[CommandHandler('start', start), CommandHandler('cancel', cancel)]
        )
        
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(conv_handler)
        
        print("✅ البوت جاهز للعمل...")
        print("🤖 البوت يعمل...")
        updater.start_polling()
        updater.idle()
        
    except Exception as e:
        print(f"❌ خطأ أثناء تشغيل البوت: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    print("========================================")
    print("  🤖 تشغيل بوت إدارة الحسابات المالية")
    print("========================================")
    print("\n🚀 جاري تشغيل البوت...")
    print("📋 اضغط Ctrl+C لإيقاف البوت\n")
    
    main()
    
    print("\n========================================")
    print(" ⏹️  تم إيقاف البوت")
    print("========================================")