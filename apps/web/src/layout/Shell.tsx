import { NavLink, Outlet } from "react-router";
import { useAuth } from "../auth/AuthContext";
import { Button } from "../components/ui";

export interface NavItem {
  to: string;
  label: string;
  end?: boolean;
}

export const ADMIN_NAV: NavItem[] = [
  { to: "/admin", label: "Orders", end: true },
  { to: "/admin/vendors", label: "Vendors" },
  { to: "/admin/customers", label: "Customers" },
  { to: "/admin/staff", label: "Admins" },
  { to: "/admin/pricing", label: "Pricing" },
  { to: "/admin/cities", label: "Cities" },
  { to: "/admin/finance/revenue", label: "Revenue" },
  { to: "/admin/finance/cod", label: "COD pending" },
  { to: "/admin/finance/payouts", label: "Vendor payouts" },
  { to: "/admin/finance/refunds", label: "Refunds" },
  { to: "/admin/audit", label: "Audit log" },
  { to: "/admin/settings", label: "Settings" },
];

export const VENDOR_NAV: NavItem[] = [{ to: "/vendor", label: "Print queue", end: true }];

/** Sidebar layout shared by the admin and vendor areas. */
export function Shell({ title, nav }: { title: string; nav: NavItem[] }) {
  const { user, logout } = useAuth();
  return (
    <div className="flex min-h-screen flex-col md:flex-row">
      <aside className="border-b border-slate-200 bg-white md:w-56 md:border-r md:border-b-0">
        <div className="px-4 py-4">
          <p className="text-lg font-semibold text-brand-800">KitaabOnDemand</p>
          <p className="text-xs text-slate-500">{title}</p>
        </div>
        <nav aria-label="Main" className="flex gap-1 overflow-x-auto px-2 pb-2 md:flex-col md:pb-4">
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `rounded-md px-3 py-2 text-sm whitespace-nowrap ${isActive ? "bg-brand-50 font-medium text-brand-800" : "text-slate-700 hover:bg-slate-100"}`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="flex items-center justify-end gap-3 border-b border-slate-200 bg-white px-4 py-2 text-sm">
          <span className="text-slate-600">{user?.full_name ?? user?.email}</span>
          <Button variant="ghost" onClick={() => void logout()}>
            Sign out
          </Button>
        </div>
        <main className="flex-1 p-4 md:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
