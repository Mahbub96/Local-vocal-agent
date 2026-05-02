export const NAV_ITEMS = ["Home", "Chat", "Memory", "Files", "Tools", "Search", "Settings"] as const;

export type NavItem = (typeof NAV_ITEMS)[number];
