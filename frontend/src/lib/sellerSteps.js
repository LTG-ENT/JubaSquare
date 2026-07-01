/**
 * Canonical seller onboarding steps (shared between the full Guide page,
 * the dashboard progress card, and the first-login wizard).
 *
 * The `id` values MUST stay in sync with backend _ONBOARDING_STEPS in
 * server.py. `titleKey` / `descKey` / `actionLabelKey` are i18n keys.
 */
import {
  UserRound, Store, Package, Truck, Wallet,
  ClipboardList, BarChart3, Upload, MessagesSquare,
} from "lucide-react";

export const SELLER_STEPS = [
  {
    id: "profile",
    icon: UserRound,
    titleKey: "guide.profile.title",
    descKey: "guide.profile.desc",
    actionLabelKey: "guide.profile.action",
    to: "/settings",
    core: true,
  },
  {
    id: "shop",
    icon: Store,
    titleKey: "guide.shop.title",
    descKey: "guide.shop.desc",
    actionLabelKey: "guide.shop.action",
    to: "/seller?tab=shops",
    core: true,
  },
  {
    id: "product",
    icon: Package,
    titleKey: "guide.product.title",
    descKey: "guide.product.desc",
    actionLabelKey: "guide.product.action",
    to: "/seller?tab=products",
    core: true,
  },
  {
    id: "delivery",
    icon: Truck,
    titleKey: "guide.delivery.title",
    descKey: "guide.delivery.desc",
    actionLabelKey: "guide.delivery.action",
    to: "/seller?tab=shops",
    core: true,
  },
  {
    id: "payout",
    icon: Wallet,
    titleKey: "guide.payout.title",
    descKey: "guide.payout.desc",
    actionLabelKey: "guide.payout.action",
    to: "/seller?tab=wallet",
    core: true,
  },
  {
    id: "orders",
    icon: ClipboardList,
    titleKey: "guide.orders.title",
    descKey: "guide.orders.desc",
    actionLabelKey: "guide.orders.action",
    to: "/seller?tab=wallet",
    core: false,
  },
  {
    id: "analytics",
    icon: BarChart3,
    titleKey: "guide.analytics.title",
    descKey: "guide.analytics.desc",
    actionLabelKey: "guide.analytics.action",
    to: "/seller?tab=analytics",
    core: false,
  },
  {
    id: "bulk",
    icon: Upload,
    titleKey: "guide.bulk.title",
    descKey: "guide.bulk.desc",
    actionLabelKey: "guide.bulk.action",
    to: "/seller?tab=products",
    core: false,
  },
  {
    id: "reviews",
    icon: MessagesSquare,
    titleKey: "guide.reviews.title",
    descKey: "guide.reviews.desc",
    actionLabelKey: "guide.reviews.action",
    to: "/seller?tab=messages",
    core: false,
  },
];

// Steps included in the compact "first-login wizard" (in this order):
// Setup shop → Add first product → Configure delivery zones.
export const WIZARD_STEP_IDS = ["shop", "product", "delivery"];
