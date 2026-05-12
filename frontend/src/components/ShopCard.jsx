import { CheckCircle2, Clock, MapPin, ArrowRight, Star } from "lucide-react";
import { Link } from "react-router-dom";

export default function ShopCard({ shop, productsPreview = [] }) {
  const verified = shop.verification === "Verified";
  return (
    <div
      data-testid={`shop-card-${shop.id}`}
      className="js-card overflow-hidden flex flex-col group hover:-translate-y-1 hover:shadow-xl transition-all duration-300"
    >
      <Link to={`/shop/${shop.id}`} className="block">
        <div className="aspect-[16/10] overflow-hidden bg-[#F2EBE5] relative">
          <img
            src={shop.image_url}
            alt={shop.name}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
            loading="lazy"
          />
          <div className="absolute top-3 right-3">
            {verified ? (
              <span className="bg-[#2D6A4F] text-white text-xs font-bold px-2.5 py-1 rounded-full flex items-center gap-1 shadow-md">
                <CheckCircle2 className="w-3 h-3" /> Verified
              </span>
            ) : (
              <span className="bg-[#E9C46A] text-[#1A1A1A] text-xs font-bold px-2.5 py-1 rounded-full flex items-center gap-1 shadow-md">
                <Clock className="w-3 h-3" /> {shop.verification}
              </span>
            )}
          </div>
        </div>
      </Link>

      <div className="p-5 flex flex-col flex-1">
        <p className="text-[10px] uppercase tracking-[0.18em] text-[#5C5C5C] font-bold">{shop.category}</p>
        <h3 className="font-display font-semibold text-xl text-[#1A1A1A] mt-1">{shop.name}</h3>
        <p className="text-sm text-[#5C5C5C] mt-1 line-clamp-2">{shop.description}</p>
        <div className="mt-2 flex items-center gap-3 text-xs text-[#5C5C5C]">
          <div className="flex items-center gap-1">
            <MapPin className="w-3 h-3" /> {shop.area}
          </div>
          {shop.average_rating ? (
            <div className="flex items-center gap-1" data-testid={`shop-rating-${shop.id}`}>
              <Star className="w-3.5 h-3.5 fill-[#E9C46A] text-[#E9C46A]" />
              <span className="font-semibold text-[#1A1A1A]">{shop.average_rating}</span>
              <span>({shop.review_count || 0})</span>
            </div>
          ) : (
            <div className="flex items-center gap-1 italic" data-testid={`shop-no-reviews-${shop.id}`}>
              <Star className="w-3.5 h-3.5" />
              <span>No reviews yet</span>
            </div>
          )}
        </div>

        {productsPreview.length > 0 && (
          <div className="mt-4 flex gap-2 overflow-hidden">
            {productsPreview.slice(0, 4).map((p) => (
              <Link
                key={p.id}
                to={`/product/${p.id}`}
                data-testid={`shop-preview-${shop.id}-${p.id}`}
                className="w-14 h-14 rounded-xl overflow-hidden flex-shrink-0 border border-[var(--js-border)] bg-[var(--js-subtle)] hover:scale-105 transition"
                title={p.name}
              >
                <img src={p.image_url} alt={p.name} className="w-full h-full object-cover" />
              </Link>
            ))}
          </div>
        )}

        <Link
          to={`/shop/${shop.id}`}
          data-testid={`view-shop-${shop.id}`}
          className="mt-4 inline-flex items-center justify-center gap-1.5 bg-[#C84B31] hover:bg-[#A83A23] text-white text-sm font-semibold px-4 py-2.5 rounded-full transition shadow-sm hover:shadow-md"
        >
          View Shop <ArrowRight className="w-4 h-4" />
        </Link>
      </div>
    </div>
  );
}
