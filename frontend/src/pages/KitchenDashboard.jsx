import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import Header from "@/components/Header";
import Footer from "@/components/Footer";
import { Clock, Phone, MapPin, DollarSign, CheckCircle, ChefHat, Package, Printer, Power, XCircle } from "lucide-react";
import api from "@/lib/api";
import { toast } from "sonner";

const STATUS_CONFIG = {
  pending: { label: "New Orders", color: "bg-yellow-500", icon: Clock },
  accepted: { label: "Accepted", color: "bg-blue-500", icon: CheckCircle },
  cooking: { label: "Cooking", color: "bg-orange-500", icon: ChefHat },
  ready: { label: "Ready", color: "bg-green-500", icon: Package },
  completed: { label: "Completed", color: "bg-gray-500", icon: CheckCircle },
  cancel_requested: { label: "Cancel Pending", color: "bg-yellow-600", icon: XCircle },
  cancel_approved: { label: "Cancelled", color: "bg-red-500", icon: XCircle },
  cancelled: { label: "Cancelled", color: "bg-red-500", icon: XCircle },
};

export default function KitchenDashboard() {
  const { restaurantId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  
  const [restaurant, setRestaurant] = useState(null);
  const [orders, setOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedOrder, setSelectedOrder] = useState(null);
  const [activeFilter, setActiveFilter] = useState("all");
  
  // Fetch restaurant and orders
  useEffect(() => {
    if (!user || !restaurantId) {
      navigate("/seller");
      return;
    }
    
    loadRestaurant();
    loadOrders();
    
    // Poll for new orders every 10 seconds
    const interval = setInterval(loadOrders, 10000);
    return () => clearInterval(interval);
  }, [restaurantId]); // eslint-disable-line
  
  const loadRestaurant = async () => {
    try {
      const { data } = await api.get(`/restaurants/${restaurantId}`);
      setRestaurant(data);
    } catch (err) {
      toast.error("Restaurant not found");
      navigate("/seller");
    }
  };
  
  const loadOrders = async () => {
    try {
      const { data } = await api.get(`/restaurant-orders/restaurant/${restaurantId}`);
      setOrders(data);
      setLoading(false);
    } catch (err) {
      console.error("Failed to load orders:", err);
      setLoading(false);
    }
  };
  
  const updateOrderStatus = async (orderId, newStatus) => {
    try {
      await api.put(`/restaurant-orders/${orderId}/status`, { status: newStatus });
      toast.success(`Order status updated to ${newStatus}`);
      loadOrders();
      
      // Print receipt if accepted or ready
      if (newStatus === "accepted" || newStatus === "ready") {
        printReceipt(orders.find(o => o.id === orderId));
      }
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to update order status");
    }
  };

  const toggleOpen = async () => {
    if (!restaurant) return;
    try {
      const { data } = await api.put(`/restaurants/${restaurantId}/toggle-open`);
      setRestaurant({ ...restaurant, is_open: data.is_open });
      toast.success(data.is_open ? "Restaurant is now OPEN" : "Restaurant is now CLOSED");
    } catch (err) {
      toast.error("Failed to update restaurant status");
    }
  };

  const requestCancel = async (orderId) => {
    const reason = window.prompt(
      "Reason for cancellation (will be sent to admin for approval):",
      ""
    );
    if (reason === null) return; // user hit Cancel
    try {
      await api.post(`/restaurant-orders/${orderId}/request-cancel`, { reason });
      toast.success("Cancellation request sent to admin");
      // refresh detail panel too
      setSelectedOrder(null);
      loadOrders();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Failed to request cancellation");
    }
  };
  
  const printReceipt = (order) => {
    if (!order) return;
    
    // Create a printable receipt
    const receiptWindow = window.open("", "_blank");
    receiptWindow.document.write(`
      <!DOCTYPE html>
      <html>
      <head>
        <title>Order Receipt - ${order.id}</title>
        <style>
          body { font-family: monospace; width: 300px; margin: 20px auto; }
          h1 { text-align: center; font-size: 18px; }
          .header { text-align: center; border-bottom: 2px dashed #000; padding-bottom: 10px; margin-bottom: 10px; }
          .order-info { margin: 10px 0; font-size: 12px; }
          .items { margin: 10px 0; }
          .item { display: flex; justify-content: space-between; margin: 5px 0; }
          .total { border-top: 2px dashed #000; padding-top: 10px; margin-top: 10px; font-weight: bold; }
          .footer { text-align: center; margin-top: 20px; font-size: 10px; }
        </style>
      </head>
      <body>
        <div class="header">
          <h1>${restaurant?.name || "Restaurant"}</h1>
          <div>Order #${order.id.substring(0, 8)}</div>
          <div>${new Date(order.created_at).toLocaleString()}</div>
        </div>
        
        <div class="order-info">
          <div><strong>Customer:</strong> ${order.customer_name}</div>
          <div><strong>Phone:</strong> ${order.customer_phone}</div>
          ${order.delivery_type === "delivery" ? `<div><strong>Address:</strong> ${order.customer_address}</div>` : ""}
          <div><strong>Type:</strong> ${order.delivery_type === "delivery" ? "Delivery" : "Pickup"}</div>
          <div><strong>Payment:</strong> ${order.payment_method === "cash" ? "Cash" : "Mobile Money"}</div>
        </div>
        
        <div class="items">
          <div style="border-bottom: 1px solid #000; margin-bottom: 5px; padding-bottom: 5px;">
            <strong>ITEMS</strong>
          </div>
          ${order.items.map(item => `
            <div class="item">
              <span>${item.quantity}x ${item.name}</span>
              <span>$${(item.price_usd * item.quantity).toFixed(2)}</span>
            </div>
            ${item.sides && item.sides.length > 0 ? item.sides.map(side => `
              <div class="item" style="margin-left: 20px; font-size: 11px;">
                <span>+ ${side.name}</span>
                <span>$${(side.price_usd * item.quantity).toFixed(2)}</span>
              </div>
            `).join('') : ''}
          `).join('')}
        </div>
        
        <div class="total">
          <div class="item">
            <span>Subtotal:</span>
            <span>$${order.subtotal.toFixed(2)}</span>
          </div>
          <div class="item">
            <span>Delivery Fee:</span>
            <span>$${order.delivery_fee.toFixed(2)}</span>
          </div>
          <div class="item" style="font-size: 16px;">
            <span>TOTAL:</span>
            <span>$${order.total.toFixed(2)}</span>
          </div>
        </div>
        
        ${order.note ? `<div style="margin-top: 10px; font-size: 11px;"><strong>Note:</strong> ${order.note}</div>` : ""}
        
        <div class="footer">
          Thank you for your order!<br>
          ${restaurant?.name || ""}
        </div>
      </body>
      </html>
    `);
    receiptWindow.document.close();
    
    setTimeout(() => {
      receiptWindow.print();
    }, 250);
  };
  
  // Group orders by status — must include every key in STATUS_CONFIG
  const ordersByStatus = {
    pending: orders.filter(o => o.status === "pending"),
    accepted: orders.filter(o => o.status === "accepted"),
    cooking: orders.filter(o => o.status === "cooking"),
    ready: orders.filter(o => o.status === "ready"),
    completed: orders.filter(o => o.status === "completed"),
    cancel_requested: orders.filter(o => o.status === "cancel_requested"),
    cancel_approved: orders.filter(o => o.status === "cancel_approved"),
    cancelled: orders.filter(o => o.status === "cancelled"),
  };
  
  const filteredOrders = activeFilter === "all" 
    ? orders 
    : orders.filter(o => o.status === activeFilter);
  
  if (loading) {
    return (
      <div className="min-h-screen bg-[var(--js-background)]">
        <Header />
        <div className="max-w-7xl mx-auto px-4 py-20 text-center">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-gray-200 border-t-[#C84B31]"></div>
          <p className="mt-4 text-[var(--js-text-secondary)]">Loading kitchen dashboard...</p>
        </div>
        <Footer />
      </div>
    );
  }
  
  return (
    <div className="min-h-screen bg-[var(--js-background)]">
      <Header />
      
      <div className="max-w-7xl mx-auto px-4 py-6">
        {/* Header */}
        <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            <button
              onClick={() => navigate("/seller")}
              className="text-sm text-[var(--js-text-secondary)] hover:text-[var(--js-text)] mb-2"
            >
              ← Back to Seller Dashboard
            </button>
            <h1 className="text-3xl font-bold text-[var(--js-text)]">
              {restaurant?.name} - Kitchen Dashboard
            </h1>
            <p className="text-[var(--js-text-secondary)] mt-1">
              Manage your restaurant orders in real-time
            </p>
          </div>

          {/* Open/Close toggle */}
          {restaurant && (
            <button
              onClick={toggleOpen}
              data-testid="restaurant-open-toggle"
              className={`inline-flex items-center gap-2 px-5 py-3 rounded-full font-bold text-sm shadow-sm transition ${
                restaurant.is_open
                  ? "bg-[#2D6A4F] hover:bg-[#245940] text-white"
                  : "bg-[#A3A39E] hover:bg-[#8A8A85] text-white"
              }`}
              title={restaurant.is_open ? "Click to close (stop receiving orders)" : "Click to open"}
            >
              <Power className="w-4 h-4" />
              <span data-testid="restaurant-open-label">
                {restaurant.is_open ? "● Open — accepting orders" : "● Closed — paused"}
              </span>
            </button>
          )}
        </div>
        
        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
          {Object.entries(STATUS_CONFIG).map(([status, config]) => {
            const Icon = config.icon;
            const count = ordersByStatus[status].length;
            return (
              <button
                key={status}
                onClick={() => setActiveFilter(activeFilter === status ? "all" : status)}
                className={`p-4 rounded-xl border-2 transition ${
                  activeFilter === status
                    ? "border-[#C84B31] bg-[#C84B31]/5"
                    : "border-[var(--js-border)] hover:border-[var(--js-border-hover)]"
                }`}
              >
                <div className={`${config.color} text-white w-10 h-10 rounded-full flex items-center justify-center mx-auto mb-2`}>
                  <Icon className="w-5 h-5" />
                </div>
                <div className="text-2xl font-bold text-[var(--js-text)]">{count}</div>
                <div className="text-xs text-[var(--js-text-secondary)] mt-1">{config.label}</div>
              </button>
            );
          })}
        </div>
        
        {/* Orders Grid/List */}
        <div className="grid lg:grid-cols-2 gap-6">
          {/* Orders List */}
          <div className="space-y-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold text-[var(--js-text)]">
                {activeFilter === "all" ? "All Orders" : STATUS_CONFIG[activeFilter]?.label}
              </h2>
              <button
                onClick={loadOrders}
                className="text-sm text-[#C84B31] hover:underline"
              >
                Refresh
              </button>
            </div>
            
            {filteredOrders.length === 0 ? (
              <div className="text-center py-12 text-[var(--js-text-secondary)]">
                No {activeFilter !== "all" ? STATUS_CONFIG[activeFilter]?.label.toLowerCase() : "orders"} yet
              </div>
            ) : (
              filteredOrders.map(order => {
                const config = STATUS_CONFIG[order.status];
                const Icon = config.icon;
                return (
                  <div
                    key={order.id}
                    onClick={() => setSelectedOrder(order)}
                    className={`bg-white dark:bg-[#1A1A1A] rounded-xl p-4 border-2 cursor-pointer transition ${
                      selectedOrder?.id === order.id
                        ? "border-[#C84B31]"
                        : "border-[var(--js-border)] hover:border-[var(--js-border-hover)]"
                    }`}
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <div className="font-bold text-[var(--js-text)]">
                          Order #{order.id.substring(0, 8)}
                        </div>
                        <div className="text-xs text-[var(--js-text-secondary)] mt-1">
                          {new Date(order.created_at).toLocaleString()}
                        </div>
                      </div>
                      <div className={`${config.color} text-white px-3 py-1 rounded-full text-xs font-semibold flex items-center gap-1`}>
                        <Icon className="w-3 h-3" />
                        {config.label}
                      </div>
                    </div>
                    
                    <div className="space-y-1 text-sm">
                      <div className="flex items-center gap-2 text-[var(--js-text)]">
                        <span className="font-semibold">{order.customer_name}</span>
                        <span className="text-[var(--js-text-secondary)]">• {order.delivery_type}</span>
                      </div>
                      <div className="text-[var(--js-text-secondary)]">
                        {order.items.length} item{order.items.length !== 1 ? "s" : ""} • ${order.total.toFixed(2)}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
          
          {/* Order Details */}
          <div className="sticky top-6">
            {selectedOrder ? (
              <div className="bg-white dark:bg-[#1A1A1A] rounded-xl p-6 border border-[var(--js-border)]">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="text-xl font-bold text-[var(--js-text)]">
                      Order #{selectedOrder.id.substring(0, 8)}
                    </h3>
                    <div className="text-sm text-[var(--js-text-secondary)] mt-1">
                      {new Date(selectedOrder.created_at).toLocaleString()}
                    </div>
                  </div>
                  <button
                    onClick={() => printReceipt(selectedOrder)}
                    className="p-2 hover:bg-[var(--js-subtle)] rounded-lg transition"
                    title="Print Receipt"
                  >
                    <Printer className="w-5 h-5 text-[var(--js-text)]" />
                  </button>
                </div>
                
                {/* Customer Info */}
                <div className="bg-[var(--js-subtle)] rounded-xl p-4 mb-4">
                  <div className="font-semibold text-[var(--js-text)] mb-2">Customer Details</div>
                  <div className="space-y-2 text-sm">
                    <div className="flex items-center gap-2 text-[var(--js-text)]">
                      <span className="font-medium">{selectedOrder.customer_name}</span>
                    </div>
                    <div className="flex items-center gap-2 text-[var(--js-text-secondary)]">
                      <Phone className="w-4 h-4" />
                      {selectedOrder.customer_phone}
                    </div>
                    {selectedOrder.delivery_type === "delivery" && (
                      <div className="flex items-start gap-2 text-[var(--js-text-secondary)]">
                        <MapPin className="w-4 h-4 mt-0.5" />
                        <span className="flex-1">{selectedOrder.customer_address}</span>
                      </div>
                    )}
                    <div className="flex items-center gap-2 text-[var(--js-text-secondary)]">
                      <DollarSign className="w-4 h-4" />
                      {selectedOrder.payment_method === "cash" ? "Cash on Delivery" : "Mobile Money"}
                    </div>
                  </div>
                </div>
                
                {/* Items */}
                <div className="mb-4">
                  <div className="font-semibold text-[var(--js-text)] mb-2">Order Items</div>
                  <div className="space-y-2">
                    {selectedOrder.items.map((item, idx) => (
                      <div key={idx} className="flex justify-between text-sm">
                        <div className="flex-1">
                          <div className="font-medium text-[var(--js-text)]">
                            {item.quantity}x {item.name}
                          </div>
                          {item.sides && item.sides.length > 0 && (
                            <div className="text-xs text-[var(--js-text-secondary)] mt-1 ml-4">
                              + {item.sides.map(s => s.name).join(", ")}
                            </div>
                          )}
                        </div>
                        <div className="font-semibold text-[var(--js-text)]">
                          ${(item.price_usd * item.quantity).toFixed(2)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                
                {/* Total */}
                <div className="border-t border-[var(--js-border)] pt-4 mb-4">
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-[var(--js-text-secondary)]">Subtotal</span>
                    <span className="text-[var(--js-text)]">${selectedOrder.subtotal.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-sm mb-2">
                    <span className="text-[var(--js-text-secondary)]">Delivery Fee</span>
                    <span className="text-[var(--js-text)]">${selectedOrder.delivery_fee.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between text-lg font-bold">
                    <span className="text-[var(--js-text)]">Total</span>
                    <span className="text-[#C84B31]">${selectedOrder.total.toFixed(2)}</span>
                  </div>
                </div>
                
                {/* Note */}
                {selectedOrder.note && (
                  <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-3 mb-4">
                    <div className="text-sm font-semibold text-yellow-800 mb-1">Note:</div>
                    <div className="text-sm text-yellow-700">{selectedOrder.note}</div>
                  </div>
                )}
                
                {/* Actions */}
                <div className="space-y-2">
                  {selectedOrder.status === "pending" && (
                    <button
                      onClick={() => updateOrderStatus(selectedOrder.id, "accepted")}
                      className="w-full bg-blue-500 hover:bg-blue-600 text-white font-bold py-3 rounded-xl transition"
                    >
                      Accept Order
                    </button>
                  )}
                  
                  {selectedOrder.status === "accepted" && (
                    <button
                      onClick={() => updateOrderStatus(selectedOrder.id, "cooking")}
                      className="w-full bg-orange-500 hover:bg-orange-600 text-white font-bold py-3 rounded-xl transition"
                    >
                      Start Cooking
                    </button>
                  )}
                  
                  {selectedOrder.status === "cooking" && (
                    <button
                      onClick={() => updateOrderStatus(selectedOrder.id, "ready")}
                      className="w-full bg-green-500 hover:bg-green-600 text-white font-bold py-3 rounded-xl transition"
                    >
                      Mark Ready
                    </button>
                  )}
                  
                  {selectedOrder.status === "ready" && (
                    <button
                      onClick={() => updateOrderStatus(selectedOrder.id, "completed")}
                      className="w-full bg-gray-600 hover:bg-gray-700 text-white font-bold py-3 rounded-xl transition"
                    >
                      Mark Completed
                    </button>
                  )}
                  
                  {selectedOrder.status === "completed" && (
                    <div className="text-center py-6 text-[var(--js-text-secondary)]">
                      Order completed ✓
                    </div>
                  )}

                  {/* Request Cancellation — visible while order is in-progress */}
                  {["accepted", "cooking", "ready"].includes(selectedOrder.status) && (
                    <button
                      onClick={() => requestCancel(selectedOrder.id)}
                      data-testid="request-cancel-btn"
                      className="w-full bg-white hover:bg-red-50 text-red-600 border-2 border-red-300 hover:border-red-500 font-semibold py-3 rounded-xl transition"
                    >
                      Request Cancellation (admin approval)
                    </button>
                  )}

                  {selectedOrder.status === "cancel_requested" && (
                    <div className="rounded-xl bg-yellow-50 border border-yellow-300 p-4 text-sm text-yellow-800" data-testid="cancel-pending-banner">
                      <div className="font-bold mb-1">Cancellation pending admin review</div>
                      <div className="text-xs">
                        Previous status: <span className="font-semibold">{selectedOrder.previous_status || "—"}</span>
                      </div>
                      {selectedOrder.cancel_reason && (
                        <div className="text-xs mt-1">Reason: {selectedOrder.cancel_reason}</div>
                      )}
                    </div>
                  )}

                  {(selectedOrder.status === "cancel_approved" || selectedOrder.status === "cancelled") && (
                    <div className="rounded-xl bg-red-50 border border-red-300 p-4 text-sm text-red-700 text-center font-semibold">
                      Order cancelled
                    </div>
                  )}
                </div>
              </div>
            ) : (
              <div className="bg-white dark:bg-[#1A1A1A] rounded-xl p-12 border border-[var(--js-border)] text-center">
                <p className="text-[var(--js-text-secondary)]">
                  Select an order to view details
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
      
      <Footer />
    </div>
  );
}
