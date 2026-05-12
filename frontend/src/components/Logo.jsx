export const LOGO_URL = "https://customer-assets.emergentagent.com/job_aee1f7c2-260b-4777-9eed-885cf7414a02/artifacts/n3n9far6_ChatGPT%20Image%20May%2012%2C%202026%2C%2010_10_27%20PM.png";

export const Logo = ({ size = 40, className = "" }) => (
  <div
    style={{ width: size, height: size }}
    className={`relative flex items-center justify-center ${className}`}
  >
    <img
      src={LOGO_URL}
      alt="JubaSquare"
      className="w-full h-full"
      style={{ objectFit: "contain", background: "transparent" }}
      loading="eager"
      decoding="async"
    />
  </div>
);
