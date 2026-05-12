export const LOGO_URL = "https://customer-assets.emergentagent.com/job_aee1f7c2-260b-4777-9eed-885cf7414a02/artifacts/n3n9far6_ChatGPT%20Image%20May%2012%2C%202026%2C%2010_10_27%20PM.png";

export const Logo = ({ size = 40, className = "" }) => (
  <div 
    style={{ 
      width: size, 
      height: size,
      overflow: 'hidden',
      position: 'relative'
    }}
    className={`${className}`}
  >
    <img
      src={LOGO_URL}
      alt="JubaSquare"
      className="absolute inset-0 w-full h-full object-cover"
      style={{ 
        mixBlendMode: 'normal', 
        background: 'transparent',
        transform: 'scale(1.1)',
        objectFit: 'cover'
      }}
      loading="eager"
      decoding="async"
    />
  </div>
);
