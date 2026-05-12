import { useState } from 'react';

/**
 * Optimized Image Component with lazy loading and placeholder
 * @param {string} src - Image source URL
 * @param {string} alt - Alt text
 * @param {string} className - CSS classes
 * @param {string} placeholderColor - Placeholder background color
 */
export default function OptimizedImage({ 
  src, 
  alt, 
  className = "", 
  placeholderColor = "#f3f4f6",
  ...props 
}) {
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);

  return (
    <div className={`relative ${className}`} style={{ backgroundColor: loaded ? 'transparent' : placeholderColor }}>
      {!error ? (
        <img
          src={src}
          alt={alt}
          className={`${className} transition-opacity duration-300 ${loaded ? 'opacity-100' : 'opacity-0'}`}
          loading="lazy"
          decoding="async"
          onLoad={() => setLoaded(true)}
          onError={() => setError(true)}
          {...props}
        />
      ) : (
        <div className={`${className} flex items-center justify-center bg-gray-200 text-gray-400 text-xs`}>
          No image
        </div>
      )}
    </div>
  );
}
