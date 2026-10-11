import { useEffect, useRef } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";

export const AuthCallback = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { loginWithGoogleSession } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;
    const sessionId = new URLSearchParams(location.hash.slice(1)).get("session_id");
    (async () => {
      const res = await loginWithGoogleSession(sessionId);
      if (!res.ok) {
        toast.error(res.error);
        navigate("/login", { replace: true });
        return;
      }
      toast.success(`Welcome, ${res.user.name}!`);
      const dest = res.user.role === "admin" ? "/admin" : res.user.role === "seller" ? "/seller" : res.user.role === "driver" ? "/driver" : "/";
      navigate(dest, { replace: true });
    })();
  }, [location.hash, loginWithGoogleSession, navigate]);

  return <div data-testid="auth-callback" className="min-h-screen" />;
};
