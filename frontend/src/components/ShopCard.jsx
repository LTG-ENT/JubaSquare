import { CheckCircle2, Clock, MapPin } from "lucide-react";
import { Link } from "react-router-dom";

export default function ShopCard({ shop }) {
  const verified = shop.verification === "Verified";
  return (
    <Link
      to={`/marketplace?shop=${shop.id}`}
      data-testid={`shop-card-${shop.id}`}
      className="js-card overflow-hidden flex flex-col group"
    >
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
      <div className="p-4">
        <p className="text-[10px] uppercase tracking-[0.18em] text-[#5C5C5C] font-bold">{shop.category}</p>
        <h3 className="font-display font-semibold text-lg text-[#1A1A1A] mt-0.5">{shop.name}</h3>
        <p className="text-sm text-[#5C5C5C] mt-1 line-clamp-2">{shop.description}</p>
        <div className="mt-3 flex items-center gap-1 text-xs text-[#5C5C5C]">
          <MapPin className="w-3 h-3" /> {shop.area}
        </div>
      </div>
    </Link>
  );
}
