import sqlite3

DB_FILE = r"C:\Users\rboss\Downloads\parana.db"


def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _display_options(all_options, title, type_):
    option_num = 1
    option_list = []

    print("\n", title, "\n")
    for option in all_options:
        code = option[0]
        desc = option[1]
        print("{0}. {1}".format(option_num, desc))
        option_num += 1
        option_list.append(code)

    selected_option = 0
    while selected_option > len(option_list) or selected_option == 0:
        prompt = "Enter the number against the " + type_ + " you want to choose: "
        try:
            selected_option = int(input(prompt))
        except ValueError:
            print("Please enter a valid number.")

    return option_list[selected_option - 1]


def login_shopper():
    conn = get_connection()
    shopper_id = input("Please enter your Shopper ID: ")
    cursor = conn.cursor()
    cursor.execute("SELECT shopper_first_name FROM shoppers WHERE shopper_id = ?", (shopper_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        print(f"\nWelcome, {row[0]}!\n")
        return int(shopper_id)
    else:
        print("\nError: Shopper ID not found. Exiting...\n")
        exit()


def show_main_menu():
    print("""
    PARANÁ – SHOPPER MAIN MENU

    1. Display your order history
    2. Add an item to your basket
    3. View your basket
    4. Change the quantity of an item in your basket
    5. Remove an item from your basket
    6. Checkout
    7. Exit
    """)
    choice = input("Enter your choice (1–7): ").strip()
    if choice not in [str(i) for i in range(1, 8)]:
        print("\n❌ Invalid option. Please enter a number 1–7.\n")
        return None
    return choice


def display_order_history(shopper_id):
    """Display the order history for the given shopper, based on Query B requirements."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            s.shopper_first_name AS shopper_first_name,
            s.shopper_surname AS shopper_surname,
            o.order_id,
            strftime('%d-%m-%Y', o.order_date) AS order_date,
            p.product_description,
            sel.seller_name,
            op.quantity AS qty_ordered,
            printf('£%.2f', op.price) AS price,
            op.ordered_product_status AS order_status
        FROM shoppers s
        JOIN shopper_orders o ON s.shopper_id = o.shopper_id
        JOIN ordered_products op ON o.order_id = op.order_id
        JOIN products p ON op.product_id = p.product_id
        JOIN sellers sel ON op.seller_id = sel.seller_id
        WHERE s.shopper_id = ?
        ORDER BY o.order_date DESC;
    """, (shopper_id,))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("\n📋 No orders found in your history.\n")
        return

    print("\n📋 Your Order History:")
    print("Shopper: {} {}".format(rows[0][0], rows[0][1]))  # Assuming all rows have same shopper
    print("-" * 80)
    print("Order ID | Order Date | Product Description | Seller Name | Qty | Price | Status")
    print("-" * 80)

    for row in rows:
        order_id, order_date, prod_desc, seller, qty, price, status = row[2], row[3], row[4], row[5], row[6], row[7], row[8]
        print(f"{order_id:8} | {order_date:10} | {prod_desc:20} | {seller:10} | {qty:3} | {price:6} | {status}")

    print("\n")


def get_or_create_basket(shopper_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT basket_id
        FROM shopper_baskets
        WHERE shopper_id = ?
        AND DATE(basket_created_date_time) = DATE('now')
        ORDER BY basket_created_date_time DESC
        LIMIT 1;
    """, (shopper_id,))
    row = cursor.fetchone()

    if row:
        conn.close()
        return row[0]
    else:
        cursor.execute("""
            INSERT INTO shopper_baskets (shopper_id, basket_created_date_time)
            VALUES (?, datetime('now'));
        """, (shopper_id,))
        conn.commit()
        basket_id = cursor.lastrowid
        conn.close()
        return basket_id


def add_item_to_basket(shopper_id):
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Select category
    cursor.execute("SELECT category_id, category_description FROM categories ORDER BY category_description;")
    categories = cursor.fetchall()
    category_id = _display_options(categories, "Select a product category:", "category")

    # 2. Select product
    cursor.execute("""
        SELECT product_id, product_description
        FROM products
        WHERE category_id = ?
        ORDER BY product_description;
    """, (category_id,))
    products = cursor.fetchall()
    product_id = _display_options(products, "Select a product:", "product")

    # 3. Select seller
    cursor.execute("""
        SELECT s.seller_id, s.seller_name || ' (£' || printf('%.2f', ps.price) || ')' AS seller_info
        FROM product_sellers ps
        JOIN sellers s ON ps.seller_id = s.seller_id
        WHERE ps.product_id = ?
        ORDER BY s.seller_name;
    """, (product_id,))
    sellers = cursor.fetchall()
    seller_id = _display_options(sellers, "Select a seller for this product:", "seller")

    # 4. Enter quantity
    quantity = 0
    while quantity <= 0:
        try:
            quantity = int(input("Enter quantity (must be > 0): "))
            if quantity <= 0:
                print("❌ Quantity must be greater than 0.")
        except ValueError:
            print("❌ Invalid input. Please enter a number.")

    # 5. Get price
    cursor.execute("""
        SELECT price
        FROM product_sellers
        WHERE product_id = ? AND seller_id = ?;
    """, (product_id, seller_id))
    price_result = cursor.fetchone()
    if not price_result:
        print("❌ Price not found for selected seller.")
        conn.close()
        return
    price = price_result[0]

    # 6. Get or create basket
    basket_id = get_or_create_basket(shopper_id)

    # 7. Insert or update basket_contents
    cursor.execute("""
        SELECT rowid, quantity
        FROM basket_contents
        WHERE basket_id = ? AND product_id = ? AND seller_id = ?;
    """, (basket_id, product_id, seller_id))
    row = cursor.fetchone()

    if row:
        new_quantity = row[1] + quantity
        cursor.execute("""
            UPDATE basket_contents
            SET quantity = ?
            WHERE rowid = ?;
        """, (new_quantity, row[0]))
    else:
        cursor.execute("""
            INSERT INTO basket_contents (basket_id, product_id, seller_id, quantity, price)
            VALUES (?, ?, ?, ?, ?);
        """, (basket_id, product_id, seller_id, quantity, price))

    conn.commit()
    conn.close()
    print("\n✅ Item added to your basket.\n")


def view_basket(shopper_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT bc.basket_id, p.product_description, s.seller_name,
               bc.quantity, bc.price, (bc.quantity * bc.price) AS total
        FROM basket_contents bc
        JOIN products p ON bc.product_id = p.product_id
        JOIN sellers s ON bc.seller_id = s.seller_id
        JOIN shopper_baskets b ON bc.basket_id = b.basket_id
        WHERE b.shopper_id = ?
        AND DATE(b.basket_created_date_time) = DATE('now');
    """, (shopper_id,))

    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("\n🛒 Your basket is empty.\n")
        return

    print("\n🛒 Your Basket:")
    grand_total = 0
    for row in rows:
        _, product, seller, qty, price, total = row
        print(f"- {product} from {seller}: {qty} x £{price:.2f} = £{total:.2f}")
        grand_total += total

    print(f"\n💳 Basket Total: £{grand_total:.2f}")


def change_item_quantity(shopper_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT basket_id FROM shopper_baskets
        WHERE shopper_id = ? AND DATE(basket_created_date_time) = DATE('now')
        ORDER BY basket_created_date_time DESC LIMIT 1;
    """, (shopper_id,))
    row = cursor.fetchone()

    if not row:
        print("\n⚠️ No active basket.\n")
        conn.close()
        return

    basket_id = row[0]

    cursor.execute("""
        SELECT bc.rowid, p.product_description, bc.quantity
        FROM basket_contents bc
        JOIN products p ON bc.product_id = p.product_id
        WHERE bc.basket_id = ?;
    """, (basket_id,))
    items = cursor.fetchall()

    if not items:
        print("\n⚠️ Basket is empty.\n")
        conn.close()
        return

    print("\n🛠️ Current Basket:")
    for item in items:
        print(f"{item[0]}. {item[1]} (Quantity: {item[2]})")

    try:
        item_id = int(input("\nEnter the item ID to update: "))
        new_qty = int(input("Enter new quantity: "))
    except ValueError:
        print("\n❌ Invalid input.\n")
        conn.close()
        return

    if new_qty <= 0:
        print("\n❌ Quantity must be greater than 0.")
        conn.close()
        return

    # Verify item exists
    cursor.execute("""
        SELECT rowid FROM basket_contents WHERE rowid = ? AND basket_id = ?;
    """, (item_id, basket_id))
    if not cursor.fetchone():
        print("\n❌ Item ID not found in your basket.\n")
        conn.close()
        return

    cursor.execute("""
        UPDATE basket_contents
        SET quantity = ?
        WHERE rowid = ?;
    """, (new_qty, item_id))

    conn.commit()
    conn.close()
    print("\n✅ Quantity updated.\n")


def remove_item_from_basket(shopper_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT basket_id FROM shopper_baskets
        WHERE shopper_id = ? AND DATE(basket_created_date_time) = DATE('now')
        ORDER BY basket_created_date_time DESC LIMIT 1;
    """, (shopper_id,))
    row = cursor.fetchone()

    if not row:
        print("\n⚠️ No active basket.\n")
        conn.close()
        return

    basket_id = row[0]

    cursor.execute("""
        SELECT bc.rowid, p.product_description, bc.quantity
        FROM basket_contents bc
        JOIN products p ON bc.product_id = p.product_id
        WHERE bc.basket_id = ?;
    """, (basket_id,))
    items = cursor.fetchall()

    if not items:
        print("\n⚠️ Basket is empty.\n")
        conn.close()
        return

    print("\n🗑️ Basket Items:")
    for item in items:
        print(f"{item[0]}. {item[1]} (Quantity: {item[2]})")

    try:
        item_id = int(input("\nEnter the item ID to remove: "))
    except ValueError:
        print("\n❌ Invalid input.\n")
        conn.close()
        return

    # Verify item exists
    cursor.execute("""
        SELECT rowid FROM basket_contents WHERE rowid = ? AND basket_id = ?;
    """, (item_id, basket_id))
    if not cursor.fetchone():
        print("\n❌ Item ID not found in your basket.\n")
        conn.close()
        return

    cursor.execute("DELETE FROM basket_contents WHERE rowid = ?;", (item_id,))
    conn.commit()
    conn.close()

    print("\n✅ Item removed from basket.\n")


def checkout(shopper_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT basket_id
        FROM shopper_baskets
        WHERE shopper_id = ? AND DATE(basket_created_date_time) = DATE('now')
        ORDER BY basket_created_date_time DESC LIMIT 1;
    """, (shopper_id,))
    row = cursor.fetchone()

    if not row:
        print("\n⚠️ No active basket.\n")
        conn.close()
        return

    basket_id = row[0]

    cursor.execute("""
        SELECT p.product_description, s.seller_name, bc.quantity, bc.price,
               (bc.quantity * bc.price) AS total
        FROM basket_contents bc
        JOIN products p ON bc.product_id = p.product_id
        JOIN sellers s ON bc.seller_id = s.seller_id
        WHERE bc.basket_id = ?;
    """, (basket_id,))
    items = cursor.fetchall()

    if not items:
        print("\n⚠️ Your basket is empty.\n")
        conn.close()
        return

    print("\n🧾 Checkout Receipt:")
    grand_total = 0
    for product, seller, qty, price, total in items:
        print(f"- {product} from {seller}: {qty} x £{price:.2f} = £{total:.2f}")
        grand_total += total

    print(f"\n💳 Grand Total: £{grand_total:.2f}")

    confirm = input("\nProceed to checkout? (y/n): ").strip().lower()
    if confirm != 'y':
        print("\nCheckout cancelled.\n")
        conn.close()
        return

    # Insert order with order_status set to 'Placed' to satisfy CHECK constraint
    cursor.execute("""
        INSERT INTO shopper_orders (shopper_id, order_date, order_status)
        VALUES (?, date('now'), 'Placed');
    """, (shopper_id,))
    order_id = cursor.lastrowid

    # Copy basket contents → ordered_products with initial status
    cursor.execute("""
        INSERT INTO ordered_products (order_id, product_id, seller_id, quantity, price, ordered_product_status)
        SELECT ?, product_id, seller_id, quantity, price, 'Placed'
        FROM basket_contents
        WHERE basket_id = ?;
    """, (order_id, basket_id))

    # Clear basket contents
    cursor.execute("DELETE FROM basket_contents WHERE basket_id = ?;", (basket_id,))
    conn.commit()
    conn.close()

    print(f"\n✅ Checkout complete! Order ID: {order_id}\n")


# --- MAIN PROGRAM LOOP ---
if __name__ == "__main__":
    shopper_id = login_shopper()

    while True:
        choice = show_main_menu()
        if choice == "1":
            display_order_history(shopper_id)
        elif choice == "2":
            add_item_to_basket(shopper_id)
        elif choice == "3":
            view_basket(shopper_id)
        elif choice == "4":
            change_item_quantity(shopper_id)
        elif choice == "5":
            remove_item_from_basket(shopper_id)
        elif choice == "6":
            checkout(shopper_id)
        elif choice == "7":
            print("Goodbye!")
            break
