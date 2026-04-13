$(document).ready(function () {
    function initPretixFormHandlers($scope) {
        if (typeof form_handlers === 'function') {
            form_handlers($scope);
        }
    }

    function reinitGenericSelect2($element) {
        if ($element.hasClass('select2-hidden-accessible')) {
            $element.select2('destroy');
        }
        $element.select2({
            closeOnSelect: !$element.prop('multiple'),
            theme: 'bootstrap',
            delay: 100,
            allowClear: !$element.prop('required'),
            width: '100%',
            language: $('body').attr('data-select2-locale'),
            placeholder: $element.attr('data-placeholder') || '',
            ajax: {
                url: $element.attr('data-select2-url'),
                data: function (params) {
                    return {
                        query: params.term,
                        page: params.page || 1
                    };
                }
            }
        });
    }

    function initCategoryWatcher($scope) {
        $scope.find('[id$="-category"]').off('change.mtg').on('change.mtg', function () {
            const $category = $(this);
            const catId = $category.val() || 0;
            const productId = $category.attr('id').replace('-category', '-product');
            const $product = $('#' + productId);

            const oldUrl = $product.attr('data-select2-url') || '';
            const parts = oldUrl.split('/');
            if (parts.length < 7) {
                return;
            }
            const newUrl = `/control/event/${parts[3]}/${parts[4]}/${catId}/items`;
            $product.attr('data-select2-url', newUrl);
            $product.val(null).trigger('change');
            reinitGenericSelect2($product);
        });
    }

    function togglePersonalizedFields($scope) {
        $scope.find('[id$="-personalized"]').each(function () {
            const $checkbox = $(this);
            const baseId = $checkbox.attr('id').replace('-personalized', '');
            const $firstNameGroup = $('#' + baseId + '-attendee_first_name').closest('.form-group');
            const $lastNameGroup = $('#' + baseId + '-attendee_last_name').closest('.form-group');
            const $companyField = $('#' + baseId + '-attendee_company');
            const $companyGroup = $companyField.length ? $companyField.closest('.form-group') : null;

            const setVisibility = () => {
                const show = $checkbox.is(':checked');
                $firstNameGroup.toggle(show);
                $lastNameGroup.toggle(show);
                if ($companyGroup) {
                    $companyGroup.toggle(show);
                }
            };

            $checkbox.off('change.mtg').on('change.mtg', setVisibility);
            setVisibility();
        });
    }

    function toggleEmailVisibility() {
        const separateOrders = $('#id_separate_orders').is(':checked');
        $('[data-row]').each(function (idx) {
            const $row = $(this);
            const $emailInput = $row.find('[id$="-attendee_email"]');
            if (!$emailInput.length) {
                return;
            }
            const $emailGroup = $emailInput.closest('.form-group');
            const showEmail = separateOrders || idx === 0;
            $emailGroup.toggle(showEmail);
        });
    }

    function initDynamicFeatures($scope) {
        initCategoryWatcher($scope);
        togglePersonalizedFields($scope);
        toggleEmailVisibility();
    }

    initDynamicFeatures($(document));
    $('#id_separate_orders').on('change.mtg', function () {
        toggleEmailVisibility();
    });

    $('#add-row').on('click', function () {
        const totalForms = $('#id_rows-TOTAL_FORMS');
        const formIndex = parseInt(totalForms.val(), 10);
        const template = $('#row-template').html().replace(/__prefix__/g, formIndex);
        const $newRow = $(template);
        $('[data-row]:last').after($newRow);
        totalForms.val(formIndex + 1);
        initPretixFormHandlers($newRow);
        initDynamicFeatures($newRow);
    });

    $(document).on('click', '[data-remove-row]', function () {
        const rowCount = $('[data-row]').length;
        if (rowCount <= 1) {
            return;
        }
        $(this).closest('[data-row]').remove();
        toggleEmailVisibility();
    });
});
