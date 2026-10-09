/**
 * The access token lives only in memory. The refresh token is kept in
 * sessionStorage so a page reload stays signed in, but closing the tab ends
 * the session.
 */
const REFRESH_KEY = "kitaab.refresh";
let accessToken: string | null = null;

export const tokens = {
  access: () => accessToken,
  refresh(): string | null {
    try {
      return sessionStorage.getItem(REFRESH_KEY);
    } catch {
      return null;
    }
  },
  save(access: string, refresh: string) {
    accessToken = access;
    try {
      sessionStorage.setItem(REFRESH_KEY, refresh);
    } catch {
      // Private mode: the session simply ends on reload.
    }
  },
  clear() {
    accessToken = null;
    try {
      sessionStorage.removeItem(REFRESH_KEY);
    } catch {
      // ignore
    }
  },
};
