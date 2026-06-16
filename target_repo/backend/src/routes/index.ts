/** API routes for eleven-7. All endpoints are mounted under /api/v1. */
import { Router } from 'express';
import { validateBody } from '../middleware/validate';
import * as productController from '../controllers/productController';
import * as orderController from '../controllers/orderController';
import * as deliveryController from '../controllers/deliveryController';
import * as dashboardController from '../controllers/dashboardController';
import * as serviceController from '../controllers/serviceController';
import * as promotionController from '../controllers/promotionController';
import * as paymentController from '../controllers/paymentController';
import * as supportController from '../controllers/supportController';
import * as inventoryController from '../controllers/inventoryController';

export const router = Router();

router.get('/health', (_req, res) => res.json({ status: 'ok', service: 'eleven7-api' }));

// Branded service catalog (ShelfScan, PricePilot, OrderForge, …)
router.get('/services', serviceController.getServices);

// Catalog
router.get('/products', productController.getProducts);
router.get('/products/low-stock', productController.getLowStock);

// Orders
router.post('/orders', validateBody(orderController.newOrderSchema), orderController.createOrder);
router.get('/orders', orderController.listOrders);
router.get('/orders/:id', orderController.getOrder);

// Deliveries & couriers
router.get('/couriers', deliveryController.getCouriers);
router.get('/orders/:orderId/delivery', deliveryController.getDeliveryForOrder);

// Dashboard
router.get('/dashboard/revenue', dashboardController.getRevenueSummary);

// PerksEngine — promotions & ALL Member points
router.get('/promotions', promotionController.listPromotions);
router.post('/promotions/validate', validateBody(promotionController.validateCouponSchema), promotionController.validateCoupon);
router.get('/customers/:customerId/points', promotionController.pointHistory);

// PaySwift — payments & refunds
router.get('/orders/:orderId/payments', paymentController.getPaymentsForOrder);
router.post('/payments/:id/capture', paymentController.capturePayment);
router.post('/refunds', validateBody(paymentController.refundSchema), paymentController.refundPayment);

// CareDesk — returns & support tickets
router.get('/support/tickets', supportController.listTickets);
router.post('/support/tickets', validateBody(supportController.newTicketSchema), supportController.openTicket);
router.post('/returns', validateBody(supportController.newReturnSchema), supportController.requestReturn);

// StockKeeper — per-store inventory & transfers
router.get('/stores/:storeId/low-stock', inventoryController.getLowStock);
router.post('/inventory/transfers', validateBody(inventoryController.transferSchema), inventoryController.transferStock);
