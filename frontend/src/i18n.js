import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

// Translation resources
const resources = {
  en: {
    translation: {
      // Common
      "welcome": "Welcome",
      "home": "Home",
      "marketplace": "Marketplace",
      "restaurants": "Restaurants",
      "orders": "Orders",
      "cart": "Cart",
      "profile": "Profile",
      "settings": "Settings",
      "logout": "Logout",
      "login": "Login",
      "signup": "Sign Up",
      "search": "Search",
      "loading": "Loading...",
      "save": "Save",
      "cancel": "Cancel",
      "delete": "Delete",
      "edit": "Edit",
      "view": "View",
      "back": "Back",
      "next": "Next",
      "submit": "Submit",
      "close": "Close",
      
      // Languages
      "language": "Language",
      "english": "English",
      "arabic": "Arabic (South Sudan)",
      "french": "French",
      "chinese": "Chinese",
      "hindi": "Hindi",
      "tigrinya": "Tigrinya (Eritrea)",
      "amharic": "Amharic (Ethiopia)",
    }
  },
  ar: {
    translation: {
      // Common
      "welcome": "مرحبا",
      "home": "الرئيسية",
      "marketplace": "السوق",
      "restaurants": "المطاعم",
      "orders": "الطلبات",
      "cart": "السلة",
      "profile": "الملف الشخصي",
      "settings": "الإعدادات",
      "logout": "تسجيل خروج",
      "login": "تسجيل دخول",
      "signup": "إنشاء حساب",
      "search": "بحث",
      "loading": "جاري التحميل...",
      "save": "حفظ",
      "cancel": "إلغاء",
      "delete": "حذف",
      "edit": "تعديل",
      "view": "عرض",
      "back": "رجوع",
      "next": "التالي",
      "submit": "إرسال",
      "close": "إغلاق",
      
      // Languages
      "language": "اللغة",
      "english": "الإنجليزية",
      "arabic": "العربية (جنوب السودان)",
      "french": "الفرنسية",
      "chinese": "الصينية",
      "hindi": "الهندية",
      "tigrinya": "التجرينية (إريتريا)",
      "amharic": "الأمهرية (إثيوبيا)",
    }
  },
  fr: {
    translation: {
      // Common
      "welcome": "Bienvenue",
      "home": "Accueil",
      "marketplace": "Marché",
      "restaurants": "Restaurants",
      "orders": "Commandes",
      "cart": "Panier",
      "profile": "Profil",
      "settings": "Paramètres",
      "logout": "Déconnexion",
      "login": "Connexion",
      "signup": "S'inscrire",
      "search": "Rechercher",
      "loading": "Chargement...",
      "save": "Enregistrer",
      "cancel": "Annuler",
      "delete": "Supprimer",
      "edit": "Modifier",
      "view": "Voir",
      "back": "Retour",
      "next": "Suivant",
      "submit": "Soumettre",
      "close": "Fermer",
      
      // Languages
      "language": "Langue",
      "english": "Anglais",
      "arabic": "Arabe (Soudan du Sud)",
      "french": "Français",
      "chinese": "Chinois",
      "hindi": "Hindi",
      "tigrinya": "Tigrigna (Érythrée)",
      "amharic": "Amharique (Éthiopie)",
    }
  },
  zh: {
    translation: {
      // Common
      "welcome": "欢迎",
      "home": "首页",
      "marketplace": "市场",
      "restaurants": "餐厅",
      "orders": "订单",
      "cart": "购物车",
      "profile": "个人资料",
      "settings": "设置",
      "logout": "登出",
      "login": "登录",
      "signup": "注册",
      "search": "搜索",
      "loading": "加载中...",
      "save": "保存",
      "cancel": "取消",
      "delete": "删除",
      "edit": "编辑",
      "view": "查看",
      "back": "返回",
      "next": "下一步",
      "submit": "提交",
      "close": "关闭",
      
      // Languages
      "language": "语言",
      "english": "英语",
      "arabic": "阿拉伯语（南苏丹）",
      "french": "法语",
      "chinese": "中文",
      "hindi": "印地语",
      "tigrinya": "提格雷尼亚语（厄立特里亚）",
      "amharic": "阿姆哈拉语（埃塞俄比亚）",
    }
  },
  hi: {
    translation: {
      // Common
      "welcome": "स्वागत है",
      "home": "होम",
      "marketplace": "बाज़ार",
      "restaurants": "रेस्टोरेंट",
      "orders": "ऑर्डर",
      "cart": "कार्ट",
      "profile": "प्रोफाइल",
      "settings": "सेटिंग्स",
      "logout": "लॉग आउट",
      "login": "लॉग इन",
      "signup": "साइन अप",
      "search": "खोजें",
      "loading": "लोड हो रहा है...",
      "save": "सहेजें",
      "cancel": "रद्द करें",
      "delete": "हटाएं",
      "edit": "संपादित करें",
      "view": "देखें",
      "back": "वापस",
      "next": "अगला",
      "submit": "जमा करें",
      "close": "बंद करें",
      
      // Languages
      "language": "भाषा",
      "english": "अंग्रेज़ी",
      "arabic": "अरबी (दक्षिण सूडान)",
      "french": "फ्रेंच",
      "chinese": "चीनी",
      "hindi": "हिंदी",
      "tigrinya": "तिग्रिन्या (इरिट्रिया)",
      "amharic": "अम्हारिक् (इथियोपिया)",
    }
  },
  ti: {
    translation: {
      // Common - Tigrinya (Eritrea)
      "welcome": "እንኳዕ ብደሓን መጻእኩም",
      "home": "ቤት",
      "marketplace": "ዕዳጋ",
      "restaurants": "ቤት መግቢ",
      "orders": "ትእዛዝ",
      "cart": "ዕዳጋ",
      "profile": "መግለጺ",
      "settings": "ቅኑዓት",
      "logout": "ውጻእ",
      "login": "ምእታው",
      "signup": "ምዝገባ",
      "search": "ምድላይ",
      "loading": "ይጽዕን ኣሎ...",
      "save": "ኣቐምጥ",
      "cancel": "ምስራዝ",
      "delete": "ደምስስ",
      "edit": "ምትዕርራይ",
      "view": "ምርኣይ",
      "back": "ምምላስ",
      "next": "ቀጻሊ",
      "submit": "ኣረክብ",
      "close": "ዕጸው",
      
      // Languages
      "language": "ቋንቋ",
      "english": "English",
      "arabic": "عربي",
      "french": "Français",
      "chinese": "中文",
      "hindi": "हिंदी",
      "tigrinya": "ትግርኛ (ኤርትራ)",
      "amharic": "አማርኛ",
    }
  },
  am: {
    translation: {
      // Common - Amharic (Ethiopia)
      "welcome": "እንኳን ደህና መጡ",
      "home": "መነሻ",
      "marketplace": "ገበያ",
      "restaurants": "ምግብ ቤቶች",
      "orders": "ትዕዛዞች",
      "cart": "ጋሪ",
      "profile": "መገለጫ",
      "settings": "ቅንብሮች",
      "logout": "ውጣ",
      "login": "ግባ",
      "signup": "ይመዝገቡ",
      "search": "ፈልግ",
      "loading": "በመጫን ላይ...",
      "save": "አስቀምጥ",
      "cancel": "ሰርዝ",
      "delete": "ሰርዝ",
      "edit": "አስተካክል",
      "view": "ተመልከት",
      "back": "ተመለስ",
      "next": "ቀጣይ",
      "submit": "አስገባ",
      "close": "ዝጋ",
      
      // Languages
      "language": "ቋንቋ",
      "english": "English",
      "arabic": "عربي",
      "french": "Français",
      "chinese": "中文",
      "hindi": "हिंदी",
      "tigrinya": "ትግርኛ",
      "amharic": "አማርኛ (ኢትዮጵያ)",
    }
  }
};

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources,
    fallbackLng: 'en',
    debug: false,
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
    }
  });

export default i18n;
