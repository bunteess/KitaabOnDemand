import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";
import { Spinner } from "../components/ui";
import { useAuth } from "./AuthContext";

/** Route guard: only the given role may see the children. */
export function RequireRole({ role, children }: { role: "ADMIN" | "VENDOR"; children: ReactNode }) {
  const { user, restoring } = useAuth();
  const location = useLocation();
  if (restoring) return <Spinner />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (user.role !== role)
    return <Navigate to={user.role === "VENDOR" ? "/vendor" : "/admin"} replace />;
  return <>{children}</>;
}
