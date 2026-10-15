document.addEventListener('DOMContentLoaded', function () {
    const existingCustomerSelect = document.getElementById('existingCustomerSelect');
    const customerName = document.getElementById('customerName');
    const customerPhone = document.getElementById('customerPhone');

    const medicineSelect = document.getElementById('medicineSelect');
    const itemQuantity = document.getElementById('itemQuantity');
    const addItemBtn = document.getElementById('addItemBtn');

    const cartTableBody = document.getElementById('cartTableBody');
    const emptyCartRow = document.getElementById('emptyCartRow');
    const itemsCountBadge = document.getElementById('itemsCountBadge');

    const displaySubtotal = document.getElementById('displaySubtotal');
    const discountInput = document.getElementById('discountInput');
    const taxPercentSelect = document.getElementById('taxPercentSelect');
    const displayTaxAmount = document.getElementById('displayTaxAmount');
    const displayGrandTotal = document.getElementById('displayGrandTotal');
    const completeSaleBtn = document.getElementById('completeSaleBtn');

   
    // Customer Selection Sync
    if (existingCustomerSelect) {
        function updateCustomerFields() {
            const selectedOpt =
                existingCustomerSelect.options[
                    existingCustomerSelect.selectedIndex
                ];

            if (
                existingCustomerSelect.value === 'new' ||
                existingCustomerSelect.value === 'other'
            ) {
                customerName.value =
                    existingCustomerSelect.value === 'new'
                        ? 'Walk-in Customer'
                        : '';

                customerPhone.value = '';
                customerName.readOnly = false;
                customerPhone.readOnly = false;
            } else {
                customerName.value =
                    selectedOpt.getAttribute('data-name') || '';

                customerPhone.value =
                    selectedOpt.getAttribute('data-phone') || '';

                customerName.readOnly = true;
                customerPhone.readOnly = true;
            }
        }

        existingCustomerSelect.addEventListener(
            'change',
            updateCustomerFields
        );

        updateCustomerFields();
    }


    // Add Item to Cart
    if (addItemBtn) {
        addItemBtn.addEventListener('click', function () {
            const selectedOpt = medicineSelect.options[medicineSelect.selectedIndex];
            if (!medicineSelect.value) {
                alert('Please select a medicine first.');
                return;
            }

            const medId = medicineSelect.value;
            const medName = selectedOpt.getAttribute('data-name');
            const unitPrice = parseFloat(selectedOpt.getAttribute('data-price')) || 0;
            const maxStock = parseInt(selectedOpt.getAttribute('data-stock')) || 0;
            const batchNo = selectedOpt.getAttribute('data-batch') || '';
            const qty = parseInt(itemQuantity.value) || 1;

            if (qty <= 0) {
                alert('Quantity must be at least 1.');
                return;
            }

            if (qty > maxStock) {
                alert(`Insufficient stock! Only ${maxStock} units available for ${medName}.`);
                return;
            }

            // Check if already in cart
            const existingRow = document.querySelector(`tr[data-med-id="${medId}"]`);
            if (existingRow) {
                const qtyInput = existingRow.querySelector('.row-qty');
                const newQty = parseInt(qtyInput.value) + qty;
                if (newQty > maxStock) {
                    alert(`Cannot add more than available stock (${maxStock} units).`);
                    return;
                }
                qtyInput.value = newQty;
                updateRowTotal(existingRow);
            } else {
                // Remove empty row placeholder
                if (emptyCartRow && emptyCartRow.parentNode) {
                    emptyCartRow.remove();
                }

                const row = document.createElement('tr');
                row.setAttribute('data-med-id', medId);
                row.innerHTML = `
                    <td>
                        <input type="hidden" name="medicine_id[]" value="${medId}">
                        <strong>${medName}</strong>
                    </td>
                    <td><code class="text-teal">${batchNo}</code></td>
                    <td>₹${unitPrice.toFixed(2)}</td>
                    <td>
                        <input type="number" name="quantity[]" class="form-control form-control-sm row-qty" 
                               value="${qty}" min="1" max="${maxStock}" data-unit-price="${unitPrice}">
                    </td>
                    <td class="text-end fw-bold row-total">₹${(unitPrice * qty).toFixed(2)}</td>
                    <td class="text-center">
                        <button type="button" class="btn btn-sm btn-outline-danger remove-item-btn"><i class="bi bi-trash"></i></button>
                    </td>
                `;

                // Add event listeners to row
                const qtyInput = row.querySelector('.row-qty');
                qtyInput.addEventListener('input', function () {
                    let val = parseInt(this.value) || 0;
                    if (val > maxStock) {
                        alert(`Only ${maxStock} units in stock.`);
                        this.value = maxStock;
                    } else if (val < 1) {
                        this.value = 1;
                    }
                    updateRowTotal(row);
                    calculateSummary();
                });

                row.querySelector('.remove-item-btn').addEventListener('click', function () {
                    row.remove();
                    checkEmptyCart();
                    calculateSummary();
                });

                cartTableBody.appendChild(row);
            }

            // Reset selector inputs
            medicineSelect.value = '';
            itemQuantity.value = 1;
            calculateSummary();
        });
    }

    function updateRowTotal(row) {
        const qtyInput = row.querySelector('.row-qty');
        const unitPrice = parseFloat(qtyInput.getAttribute('data-unit-price')) || 0;
        const qty = parseInt(qtyInput.value) || 0;
        const total = unitPrice * qty;
        row.querySelector('.row-total').textContent = `₹${total.toFixed(2)}`;
    }

    function checkEmptyCart() {
        const rows = cartTableBody.querySelectorAll('tr[data-med-id]');
        if (rows.length === 0) {
            cartTableBody.appendChild(emptyCartRow);
            completeSaleBtn.disabled = true;
            itemsCountBadge.textContent = '0 Items';
        } else {
            completeSaleBtn.disabled = false;
            itemsCountBadge.textContent = `${rows.length} Items`;
        }
    }

    function calculateSummary() {
        const rows = cartTableBody.querySelectorAll('tr[data-med-id]');
        let subtotal = 0;

        rows.forEach(function (row) {
            const qtyInput = row.querySelector('.row-qty');
            const unitPrice = parseFloat(qtyInput.getAttribute('data-unit-price')) || 0;
            const qty = parseInt(qtyInput.value) || 0;
            subtotal += unitPrice * qty;
        });

        const discount = parseFloat(discountInput.value) || 0;
        const taxPercent = parseFloat(taxPercentSelect.value) || 0;

        let taxableAmount = subtotal - discount;
        if (taxableAmount < 0) taxableAmount = 0;

        const taxAmount = (taxableAmount * taxPercent) / 100;
        const grandTotal = taxableAmount + taxAmount;

        displaySubtotal.textContent = `₹${subtotal.toFixed(2)}`;
        displayTaxAmount.textContent = `₹${taxAmount.toFixed(2)}`;
        displayGrandTotal.textContent = `₹${grandTotal.toFixed(2)}`;

        checkEmptyCart();
    }

    if (discountInput) discountInput.addEventListener('input', calculateSummary);
    if (taxPercentSelect) taxPercentSelect.addEventListener('change', calculateSummary);
});
