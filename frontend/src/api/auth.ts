import { api } from "./client";
import type { TokenResponse, User } from "../types/api";

export const authApi = {
  register(name: string, email: string, password: string) {
    return api<User>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ name, email, password }),
    });
  },
  login(email: string, password: string) {
    return api<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },
  refresh() {
    return api<TokenResponse>("/auth/refresh", { method: "POST" }, false);
  },
  logout() {
    return api<void>("/auth/logout", { method: "POST" }, false);
  },
  me() {
    return api<User>("/auth/me", {}, false);
  },
};
