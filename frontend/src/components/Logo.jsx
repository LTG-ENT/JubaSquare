export const LOGO_URL = "https://customer-assets.emergentagent.com/job_juba-vendors/artifacts/rr4cyen5_image.png";

export const Logo = ({ size = 40, className = "" }) => (
  <img
    src={LOGO_URL}
    alt="JubaSquare"
    width={size}
    height={size}
    className={`rounded-xl object-cover shrink-0 ${className}`}
    loading="eager"
  />
);
