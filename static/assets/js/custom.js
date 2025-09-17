// JS for new_rent.html

document.addEventListener('DOMContentLoaded', function () {
    const startDateField = document.getElementById('id_start_date');
    const nextInvoiceDateField = document.getElementById('id_next_invoice_date');
    const endDateField = document.getElementById('id_end_date');

    if (startDateField) {
        startDateField.addEventListener('change', function () {
            const startDateValue = startDateField.value;
            if (startDateValue) {
                const startDate = new Date(startDateValue);

                // Calculate next_invoice_date (30 days from start_date)
                const nextInvoiceDate = new Date(startDate);
                nextInvoiceDate.setDate(startDate.getDate() + 30);

                // Calculate end_date (1 year from start_date)
                const endDate = new Date(startDate);
                endDate.setFullYear(startDate.getFullYear() + 1);

                // Format the dates as YYYY-MM-DD
                const formatDate = (date) => {
                    const year = date.getFullYear();
                    const month = String(date.getMonth() + 1).padStart(2, '0');
                    const day = String(date.getDate()).padStart(2, '0');
                    return `${year}-${month}-${day}`;
                };

                if (nextInvoiceDateField) nextInvoiceDateField.value = formatDate(nextInvoiceDate);
                if (endDateField) nextInvoiceDateField.value = formatDate(endDate);
            } else {
                if (nextInvoiceDateField) nextInvoiceDateField.value = '';
                if (endDateField) endDateField.value = '';
            }
        });
    }
});

// JS for toggling unregistered tenant fields (new_rent.html)
function toggleUnregisteredFields(tenantFound, personalIdEntered) {
  var unregisteredFields = document.getElementById('unregistered-fields');
  if (unregisteredFields) {
    if (!tenantFound && personalIdEntered) {
      unregisteredFields.style.display = 'block';
    } else {
      unregisteredFields.style.display = 'none';
    }
  }
}

// JS for payments.html table filtering

document.addEventListener('DOMContentLoaded', function () {
  const filterInputs = {
    transactionNumber: document.getElementById('filterTransactionNumber'),
    type: document.getElementById('filterType'),
    tenant: document.getElementById('filterTenant'),
    property: document.getElementById('filterProperty'),
    fromDate: document.getElementById('filterFromDate'),
    toDate: document.getElementById('filterToDate'),
  };

  const table = document.getElementById('transactionsTable');
  if (!table) return;
  const rows = table.getElementsByTagName('tbody')[0].getElementsByTagName('tr');

  // Function to filter rows
  function filterRows() {
    for (let row of rows) {
      let show = true;
      // Add your filtering logic here
      // ...
      row.style.display = show ? '' : 'none';
    }
  }

  for (let key in filterInputs) {
    if (filterInputs[key]) {
      filterInputs[key].addEventListener('input', filterRows);
    }
  }
});
