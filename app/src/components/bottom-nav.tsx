import { Link, useLocation } from "@tanstack/react-router";
import { Home, Bell, UserRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useNotifications } from "@/components/notifications-provider";

export function BottomNav() {
  const { pathname } = useLocation();
  const { unread } = useNotifications();
  return (
    <nav aria-label="Main navigation" className="fixed inset-x-0 bottom-0 z-10 mx-auto max-w-md border-t border-border bg-card/95 pb-[env(safe-area-inset-bottom)] backdrop-blur">
      <div className="grid grid-cols-3 px-2 py-2">
        <Button asChild variant="ghost" className={`h-14 flex-col gap-1 text-xs ${pathname === "/" ? "text-primary" : "text-muted-foreground"}`}>
          <Link to="/" aria-current={pathname === "/" ? "page" : undefined}><Home className="!size-5" />Home</Link>
        </Button>
        <Button asChild variant="ghost" className={`h-14 flex-col gap-1 text-xs ${pathname === "/notifications" ? "text-primary" : "text-muted-foreground"}`}>
          <Link to="/notifications" aria-current={pathname === "/notifications" ? "page" : undefined}><span className="relative"><Bell className="!size-5" />{unread > 0 && <span className="absolute -right-2 -top-1 flex size-4 items-center justify-center rounded-full bg-destructive text-[10px] text-destructive-foreground">{unread > 9 ? "9+" : unread}</span>}</span>Notifications</Link>
        </Button>
        <Button asChild variant="ghost" className={`h-14 flex-col gap-1 text-xs ${pathname === "/profile" ? "text-primary" : "text-muted-foreground"}`}>
          <Link to="/profile" aria-current={pathname === "/profile" ? "page" : undefined}><UserRound className="!size-5" />Profile</Link>
        </Button>
      </div>
    </nav>
  );
}