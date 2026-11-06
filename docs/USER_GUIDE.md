# StockWise user guide

StockWise keeps a running count of everything on your shelves. Every sale, delivery or correction is recorded with who did it and when, so the number on screen should match the number on the shelf.

## Setting up your business

Each business on StockWise has its own private space. Other businesses can't see your products, stock, staff or reports, and you can't see theirs.

1. **Create your business:** go to the StockWise site and choose **Create an account for your business**. Enter your shop's name, your name, your email and a password. You become the business's admin.
2. **Follow the three getting-started steps** on your dashboard: add your products, invite your staff, and record stock.
3. **Invite staff:** go to **Users → Invite people**, choose Staff or Admin, and tap **Create invite link**. Send the link by WhatsApp, SMS or email. The person opens it, enters their name and a password, and is in your business straight away.
   - Each link works once and expires (1, 7 or 30 days).
   - To make sure only one person can use it, enter their email when creating it.
   - To stop a link from working, use **Cancel link** under *Pending invite links*.
   - You can also create an account for someone directly with **Add user** and give them the password.

Each email belongs to one business. Someone who works at two shops uses a different email for each.

There are two kinds of account in a business:

- **Staff** can look up products and record stock in and out.
- **Admins** can do everything staff can, and also manage products, suppliers, reports and user accounts.

## Logging in

Open StockWise in Chrome or Edge, on a computer or a phone. Enter your email and password, then tap **Log in**.

If you forget your password, ask the shop admin to set a new one for you. For security, you are logged out automatically after 8 hours. After many wrong passwords in a row, StockWise asks you to wait a few minutes before trying again.

## The dashboard

After you log in you see:

- **Two big buttons:** *Record sale / stock out* and *Record delivery / stock in*. Most days, this is all you need.
- **Totals:** how many products you carry, units on hand, and (for admins) the value of stock.
- **Reorder soon:** products at or below their reorder level. A yellow bar means low and red means out of stock. The black line on each bar marks the reorder level.
- **Latest stock changes:** the last ten things recorded, by anyone.

The dashboard updates by itself every few seconds, so you will see what colleagues record.

## Recording a sale or delivery

1. Tap **Record sale / stock out** (or **Record delivery / stock in**). On a phone, you can also use the round **Record** button at the bottom.
2. Search for the product by name or SKU and tap it.
3. Set the quantity with **−** and **+**, or type it.
4. Check the line underneath, which shows what the stock will be afterwards.
5. Optionally add a note, such as an invoice number or "damaged".
6. Tap **Record stock out** / **Record stock in**.

A message confirms the new stock level. The form stays open, so you can record the next item straight away.

## Recording stock with a barcode scanner or camera

If a product has a barcode, you can scan it instead of searching:

- **USB or Bluetooth scanner:** click the product search box, then scan. The product is selected and the cursor jumps to the quantity. Type the quantity and press Enter. The box clears, ready for the next item.
- **Phone, tablet or laptop camera:** tap **Scan** next to the search box and point the camera at the barcode. It is read automatically. The first time, your browser asks for permission to use the camera; tap **Allow**.
- **Barcode not recognised:** StockWise tells you no product has that barcode. Staff should ask an admin to add it. Admins can tap **Add it as a new product**, and the barcode is filled in for them.

Scanned and typed entries follow exactly the same rules. The audit log shows which method was used for each one.

**"Not enough stock".** If you try to remove more than the system shows, StockWise stops you and nothing is saved. If the shelf really has more than the system says, ask an admin. An admin can choose **Record anyway**, and the override is marked in the audit log.

## Products

**Products** lists everything you stock. You can:

- search by name or SKU,
- filter by category,
- tick **Low stock only**, and
- sort by lowest stock.

Tap a product to see its stock level, suppliers and full history.

**Admins only:**

- **Add product:** enter a name, a unique SKU, category, price, reorder level and the opening stock you count today. The opening stock is recorded as a stock-in.
- **Barcodes:** in the product form, scan or type the barcode printed on the packaging and press Enter, or tap the camera button. A product can have more than one, for example one for a single item and one for the carton.
- **Edit details:** change name, SKU, category, price or reorder level. To change the stock quantity itself, record a stock movement.
- **Archive:** hides a product you no longer sell. Its history is kept, and you can **Restore** it later. Products that have never had stock recorded can be deleted instead.
- **Suppliers → Change:** choose which suppliers provide this product.

## Suppliers (admins)

Add the businesses you buy from, with contact person, phone, email and address.

- A supplier with no linked products can be deleted.
- A supplier linked to products is **deactivated** instead, which keeps the record but stops it from being linked to new products. You can reactivate it at any time.

## Reports (admins)

**Stock report**

1. Pick a date range (Today, 7, 30 or 90 days, or your own dates).
2. Read the table. For each product it shows units in and out during that period, plus current stock and value.
3. To work with the data in Excel or Google Sheets, use **Export stock CSV** or **Export movements CSV**.

**Audit log.** Every stock change, showing who made it, when, how it was entered (typed, scanner or camera), how many units, the stock afterwards, and whether an override was used. Filter by user, product, in/out or method, and export to CSV.

## Users (admins)

The Users page also lets you rename your business and manage invite links (see *Setting up your business* above).

- **Add user:** set a name, email, role and starting password (at least 8 characters). Share the password with them privately.
- **Edit:** change their name or role, or set a new password.
- **Disable:** stops someone logging in, for example when they leave. Their past records stay in the audit log.

StockWise always keeps at least one active admin, and you cannot disable your own account.

## Tips for accurate stock

- Record every sale and delivery as it happens, not at the end of the day.
- Do a physical count regularly. If the shelf count differs from StockWise, record the difference as a stock in or out with the note "Count correction".
- Set reorder levels to how many you sell between ordering and the delivery arriving.
