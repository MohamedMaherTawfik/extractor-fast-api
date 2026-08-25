export type Language = "ar" | "en";

const messages = {
  ar: {
    home: "الرئيسية", content: "المحتوى", intelligence: "الذكاء", patterns: "الأنماط والوصفات", rules: "القواعد",
    generation: "التوليد", assets: "الأصول", calendar: "تقويم المحتوى", products: "المنتجات", customers: "العملاء",
    sales: "المبيعات", inventory: "المخزون", suppliers: "الموردون", msc: "استقبال MSC", conversations: "المحادثات",
    service: "خدمة العملاء", approvals: "الموافقات", analytics: "التحليلات", audit: "التدقيق", settings: "الإعدادات",
    search: "ابحث في النظام…", online: "متصل", operator: "وضع المشغّل", empty: "لا توجد بيانات حتى الآن", retry: "إعادة المحاولة",
  },
  en: {
    home: "Home", content: "Content", intelligence: "Intelligence", patterns: "Patterns & Recipes", rules: "Rules",
    generation: "Generation", assets: "Assets", calendar: "Content Calendar", products: "Products", customers: "Customers",
    sales: "Sales", inventory: "Inventory", suppliers: "Suppliers", msc: "MSC Intake", conversations: "Conversations",
    service: "Customer Service", approvals: "Approvals", analytics: "Analytics", audit: "Audit", settings: "Settings",
    search: "Search the system…", online: "Online", operator: "Operator mode", empty: "No data yet", retry: "Retry",
  },
} as const;

export function translate(language: Language, key: keyof typeof messages.en): string { return messages[language][key]; }
