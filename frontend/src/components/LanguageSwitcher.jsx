import { useState, useRef, useEffect } from 'react';
import { Globe } from 'lucide-react';
import { useTranslation } from 'react-i18next';

const LANGUAGES = [
  { code: 'en', name: 'English', nativeName: 'English', flag: '🇬🇧' },
  { code: 'ar', name: 'Arabic', nativeName: 'العربية', flag: '🇸🇸', rtl: true },
  { code: 'fr', name: 'French', nativeName: 'Français', flag: '🇫🇷' },
  { code: 'zh', name: 'Chinese', nativeName: '中文', flag: '🇨🇳' },
  { code: 'hi', name: 'Hindi', nativeName: 'हिंदी', flag: '🇮🇳' },
  { code: 'ti', name: 'Tigrinya', nativeName: 'ትግርኛ', flag: '🇪🇷' },
  { code: 'am', name: 'Amharic', nativeName: 'አማርኛ', flag: '🇪🇹' },
];

export default function LanguageSwitcher() {
  const { i18n, t } = useTranslation();
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef(null);

  const currentLanguage = LANGUAGES.find(lang => lang.code === i18n.language) || LANGUAGES[0];

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const changeLanguage = (langCode) => {
    i18n.changeLanguage(langCode);
    const lang = LANGUAGES.find(l => l.code === langCode);
    
    // Set document direction for RTL languages
    if (lang?.rtl) {
      document.documentElement.dir = 'rtl';
      document.documentElement.lang = langCode;
    } else {
      document.documentElement.dir = 'ltr';
      document.documentElement.lang = langCode;
    }
    
    setOpen(false);
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 p-2 rounded-full hover:bg-white/10 transition"
        title={t('language')}
        data-testid="language-switcher"
      >
        <Globe className="w-5 h-5 text-white" />
        <span className="text-sm font-semibold text-white hidden sm:inline">
          {currentLanguage.flag}
        </span>
      </button>

      {open && (
        <div className="absolute left-0 top-full mt-2 w-64 max-w-[calc(100vw-2rem)] bg-white rounded-xl shadow-2xl border border-[var(--js-border)] overflow-hidden z-50" dir="ltr">
          <div className="p-2 bg-[var(--js-bg)] border-b border-[var(--js-border)]">
            <p className="text-xs uppercase tracking-wider font-bold text-[var(--js-text-secondary)]">
              {t('language')}
            </p>
          </div>
          <div className="max-h-80 overflow-y-auto">
            {LANGUAGES.map((lang) => (
              <button
                key={lang.code}
                onClick={() => changeLanguage(lang.code)}
                className={`w-full text-left px-4 py-3 hover:bg-[var(--js-subtle)] transition flex items-center justify-between ${
                  i18n.language === lang.code ? 'bg-[var(--js-subtle)]' : ''
                }`}
                data-testid={`lang-${lang.code}`}
              >
                <div className="flex items-center gap-3">
                  <span className="text-2xl shrink-0">{lang.flag}</span>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-[var(--js-text)] truncate">
                      {lang.nativeName}
                    </p>
                    <p className="text-xs text-[var(--js-text-secondary)] truncate">
                      {lang.name}
                    </p>
                  </div>
                </div>
                {i18n.language === lang.code && (
                  <div className="w-2 h-2 rounded-full bg-[#C84B31] shrink-0" />
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
