export const LOGO_URL = "https://customer-assets.emergentagent.com/job_aee1f7c2-260b-4777-9eed-885cf7414a02/artifacts/n3n9far6_ChatGPT%20Image%20May%2012%2C%202026%2C%2010_10_27%20PM.png";

export const Logo = ({ size = 40, className = "" }) => (
  <img
    src={LOGO_URL}
    alt="JubaSquare"
    width={size}
    height={size}
    className={`object-contain shrink-0 ${className}`}
    style={{ mixBlendMode: 'normal', background: 'transparent' }}
    loading="eager"
  />
);
