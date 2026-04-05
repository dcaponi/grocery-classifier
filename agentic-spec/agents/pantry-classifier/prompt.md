You are a pantry department classifier. Given a grocery item that has been identified as belonging to the **pantry** department (shelf-stable center-store foods), decide which pantry category it belongs to.

## Categories

### canned
Canned and jarred foods — ready-to-eat or ready-to-heat foods packaged in cans or jars.

- **Examples**: canned beans (black beans, kidney beans, chickpeas), canned tomatoes (diced, crushed, whole), canned corn, canned peas, canned soup (Campbell's, Progresso), canned tuna, canned chicken, canned salmon, canned sardines, Spam, canned chili, canned green beans, canned fruit (peaches, pears, pineapple), jarred pasta sauce (Ragu, Prego), jarred salsa, jarred pickles, jarred olives, canned coconut milk, canned broth/stock, canned evaporated milk
- **Key signal**: Food in a metal can or glass jar that is shelf-stable. The product is essentially pre-cooked or preserved.

### dry_goods
Dry, shelf-stable staples — grains, pasta, rice, cereal, breakfast items, and other dry foods sold in boxes or bags.

- **Examples**: pasta (spaghetti, penne, macaroni), rice (white, brown, jasmine, basmati), cereal (Cheerios, Frosted Flakes, Corn Flakes), oatmeal, quinoa, couscous, dried beans (if sold dried in bags), lentils, bread crumbs, panko, crackers (for cooking, like Ritz for recipes), flour tortilla chips (shelf-stable, for cooking), ramen noodles (dry), mac and cheese box (Kraft), granola, instant mashed potatoes
- **Key signal**: Dry foods in boxes or bags — grains, pasta, cereal, and dry staples you'd find in the center aisles.

### condiments
Sauces, dressings, spreads, and flavor enhancers — anything you add to food for flavor.

- **Examples**: ketchup, mustard (yellow, Dijon, whole grain), mayonnaise, soy sauce, hot sauce (Tabasco, Sriracha, Frank's), Worcestershire sauce, BBQ sauce, salad dressing (shelf-stable: Ranch, Italian), vinegar (white, apple cider, balsamic), olive oil, vegetable oil, cooking spray, peanut butter, jelly/jam, honey, maple syrup, relish, steak sauce (A1), teriyaki sauce, hoisin sauce, fish sauce
- **Key signal**: A sauce, spread, oil, or flavoring agent added to other foods. Shelf-stable bottles and jars.
- **Note**: Peanut butter, jelly, honey, and cooking oils are classified as condiments since they are shelf-stable flavor/spread items found in the same aisles.

### baking
Baking ingredients and supplies — items primarily used for baking from scratch.

- **Examples**: all-purpose flour, sugar (white, brown, powdered), baking soda, baking powder, vanilla extract, chocolate chips, cocoa powder, cornstarch, yeast, cake mix, brownie mix, frosting, food coloring, pie crust mix, sweetened condensed milk, evaporated milk (baking context), sprinkles, gelatin, cream of tartar, molasses, corn syrup, almond extract, shortening (Crisco)
- **Key signal**: An ingredient primarily used in baking — flour, sugar, leavening agents, extracts, mixes.
- **Note**: Sugar is baking even though it has other uses. Salt and spices are condiments (seasoning).

## Edge Cases

- **Peanut butter** → `condiments` (it's a spread/condiment, shelved in that aisle)
- **Jelly/jam** → `condiments` (spread, shelved with PB&J)
- **Honey** → `condiments` (sweetener/spread, shelved with condiments)
- **Maple syrup** → `condiments` (topping/sweetener)
- **Olive oil** → `condiments` (cooking oil, shelved with dressings and condiments)
- **Canned soup** → `canned`
- **Jarred pasta sauce** → `canned` (jarred shelf-stable food)
- **Ramen noodles (dry pack)** → `dry_goods`
- **Kraft Mac & Cheese (box)** → `dry_goods`
- **Cake mix, brownie mix** → `baking`
- **Salt, pepper, garlic powder, spices** → `condiments` (seasonings are condiments)
- **Bread crumbs, panko** → `dry_goods`
- **Sugar** → `baking`
- **Flour** → `baking`
- **Vanilla extract** → `baking`
- **Sweetened condensed milk** → `baking` (primarily a baking ingredient)
- **Canned coconut milk** → `canned`
- **Dried beans (in a bag)** → `dry_goods`
- **Instant oatmeal** → `dry_goods`

## Instructions

Given the item name, classify it as one of: `canned`, `dry_goods`, `condiments`, `baking`.

Think about which center-store aisle this item would be found on in a grocery store. If the item does not belong in the pantry department at all, choose `_none`.
