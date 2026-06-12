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

    function getRowBaseId($row) {
        const $ticketCount = $row.find('input[name$="-ticket_count"]');
        if ($ticketCount.length) {
            return ($ticketCount.attr('name') || '').replace('-ticket_count', '');
        }
        const $personalized = $row.find('input[name$="-personalized"]').first();
        if ($personalized.length) {
            return ($personalized.attr('name') || '').replace('-personalized', '');
        }
        return null;
    }

    function isPersonalizedYes($row) {
        const baseId = getRowBaseId($row);
        if (!baseId) {
            return false;
        }
        const $checked = $row.find('input[name="' + baseId + '-personalized"]:checked');
        return $checked.val() === 'yes';
    }

    function getNameMode($row) {
        const baseId = getRowBaseId($row);
        if (!baseId) {
            return 'same';
        }
        const $checked = $row.find('input[name="' + baseId + '-name_mode"]:checked');
        return $checked.val() || 'same';
    }

    function getTicketCount($row) {
        const baseId = getRowBaseId($row);
        if (!baseId) {
            return 1;
        }
        const count = parseInt($row.find('input[name="' + baseId + '-ticket_count"]').val(), 10);
        return Number.isFinite(count) && count > 0 ? count : 1;
    }

    function readIndividualNames($row) {
        const baseId = getRowBaseId($row);
        const $hidden = $row.find('input[name="' + baseId + '-attendee_names_json"]');
        if (!$hidden.length || !$hidden.val()) {
            return [];
        }
        try {
            const parsed = JSON.parse($hidden.val());
            return Array.isArray(parsed) ? parsed : [];
        } catch (e) {
            return [];
        }
    }

    function writeIndividualNames($row, names) {
        const baseId = getRowBaseId($row);
        $row.find('input[name="' + baseId + '-attendee_names_json"]').val(JSON.stringify(names));
    }

    function buildIndividualNameFields($row) {
        const baseId = getRowBaseId($row);
        const $container = $row.find('.mtg-individual-names');
        const ticketCount = getTicketCount($row);
        const existing = readIndividualNames($row);
        const names = [];

        $container.empty();

        for (let i = 0; i < ticketCount; i += 1) {
            const entry = existing[i] || { first_name: '', last_name: '' };
            names.push({
                first_name: entry.first_name || '',
                last_name: entry.last_name || ''
            });

            const firstVal = $('<div>').text(names[i].first_name).html();
            const lastVal = $('<div>').text(names[i].last_name).html();
            const ticketNum = i + 1;

            const $group = $(
                '<div class="mtg-individual-name-row">' +
                '<div class="form-group mtg-ticket-heading">' +
                '<label class="col-md-3 control-label">Ticket ' + ticketNum + '</label>' +
                '<div class="col-md-9"></div>' +
                '</div>' +
                '<div class="form-group mtg-name-pair">' +
                '<label class="col-md-3 control-label"></label>' +
                '<div class="col-md-9">' +
                '<div class="row mtg-name-pair-row">' +
                '<div class="col-md-6">' +
                '<label class="control-label">Vorname</label>' +
                '<input type="text" class="form-control mtg-individual-first-name" ' +
                'data-index="' + i + '" value="' + firstVal + '">' +
                '</div>' +
                '<div class="col-md-6">' +
                '<label class="control-label">Nachname</label>' +
                '<input type="text" class="form-control mtg-individual-last-name" ' +
                'data-index="' + i + '" value="' + lastVal + '">' +
                '</div>' +
                '</div></div></div></div>'
            );
            $container.append($group);
        }

        writeIndividualNames($row, names);
    }

    function syncIndividualNamesFromInputs($row) {
        const ticketCount = getTicketCount($row);
        const names = [];

        for (let i = 0; i < ticketCount; i += 1) {
            const firstName = $row.find('.mtg-individual-first-name[data-index="' + i + '"]').val() || '';
            const lastName = $row.find('.mtg-individual-last-name[data-index="' + i + '"]').val() || '';
            names.push({
                first_name: firstName.trim(),
                last_name: lastName.trim()
            });
        }

        writeIndividualNames($row, names);
    }

    function updatePersonalizedVisibility($row) {
        const personalized = isPersonalizedYes($row);
        const nameMode = getNameMode($row);
        const $nameModeGroup = $row.find('.mtg-name-mode-group');
        const $sameNameFields = $row.find('.mtg-same-name-fields');
        const $individualNames = $row.find('.mtg-individual-names');
        const $companyField = $row.find('[id$="-attendee_company"]');
        const $companyGroup = $companyField.length ? $companyField.closest('.form-group') : null;

        $nameModeGroup.toggle(personalized);
        $sameNameFields.toggle(personalized && nameMode === 'same');
        $individualNames.toggle(personalized && nameMode === 'individual');

        if (personalized && nameMode === 'individual') {
            buildIndividualNameFields($row);
        } else if (!personalized) {
            $individualNames.empty();
            const baseId = getRowBaseId($row);
            if (baseId) {
                $row.find('input[name="' + baseId + '-attendee_names_json"]').val('');
            }
        }

        if ($companyGroup) {
            $companyGroup.toggle(personalized);
        }
    }

    function togglePersonalizedFields($scope) {
        $scope.find('[data-row]').each(function () {
            const $row = $(this);
            updatePersonalizedVisibility($row);
        });
    }

    function bindPersonalizedEvents() {
        $(document).off('change.mtgPersonalized click.mtgPersonalized', 'input[name$="-personalized"], input[name$="-name_mode"], [id$="-ticket_count"]');
        $(document).on('change.mtgPersonalized click.mtgPersonalized', 'input[name$="-personalized"], input[name$="-name_mode"], [id$="-ticket_count"]', function () {
            const $row = $(this).closest('[data-row]');
            if (!$row.length) {
                return;
            }
            updatePersonalizedVisibility($row);
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

    bindPersonalizedEvents();
    initDynamicFeatures($(document));
    $('#id_separate_orders').on('change.mtg', function () {
        toggleEmailVisibility();
    });

    $(document).on('input change', '.mtg-individual-first-name, .mtg-individual-last-name', function () {
        const $row = $(this).closest('[data-row]');
        syncIndividualNamesFromInputs($row);
    });

    $('form').on('submit', function () {
        $('[data-row]').each(function () {
            const $row = $(this);
            if (isPersonalizedYes($row) && getNameMode($row) === 'individual') {
                syncIndividualNamesFromInputs($row);
            }
        });
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
