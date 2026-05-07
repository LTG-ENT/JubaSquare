export const LOGO_URL = "/branding/jubasquare-logo.png";

export const Logo = ({ size = 40, className = "" }) => (
  <img
    src={LOGO_URL}
    alt="JubaSquare"
    width={size}
    height={size}
    className={`object-contain shrink-0 ${className}`}
    loading="eager"
  />
);
