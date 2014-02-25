import csv

from collections import OrderedDict

from django.http import HttpResponse
from django.utils.encoding import smart_str
from django.utils.translation import ugettext as _

from libya_tally.apps.tally.models.ballot import Ballot
from libya_tally.apps.tally.models.result_form import ResultForm
from libya_tally.libs.models.enums.entry_version import EntryVersion
from libya_tally.libs.models.enums.form_state import FormState


OUTPUT_PATH = 'results/candidate_votes.csv'
RESULTS_PATH = 'results/form_results.csv'
SPECIAL_BALLOTS = None


def export_to_csv_response(queryset, headers, fields, filename='data.csv'):
    response = HttpResponse(content_type='text/csv')
    response['Content-Desposition'] = 'attachment; filename=%s' % filename

    w = csv.writer(response, csv.excel)
    w.writerow([smart_str(col) for col in headers])

    for obj in queryset:
        row = []
        for field in fields:
            row.append(smart_str(getattr(obj, field)))
        w.writerow(row)

    return response


def distinct_forms(ballot):
    forms = ResultForm.distinct_filter(ballot.resultform_set)

    if not forms:
        forms = ResultForm.distinct_for_component(ballot)

    return forms


def get_votes(candidate):
    """Return the active results for this candidate that are for archived
    result forms."""
    results = candidate.results.filter(
        entry_version=EntryVersion.FINAL,
        active=True, result_form__form_state=FormState.ARCHIVED).all()

    return [len(results), sum([r.votes for r in results])]


def save_barcode_results(complete_barcodes):
    with open(RESULTS_PATH, 'w') as f:
        header = ['ballot', 'barcode', 'order', 'name', 'votes']
        w = csv.DictWriter(f, header)
        f.write(u'\ufeff'.encode('utf-8'))

        for barcode in complete_barcodes:
            result_form = ResultForm.objects.get(barcode=barcode)
            candidates = result_form.ballot.candidates.all()

            for candidate in candidates.order_by('order'):
                results = candidate.results.filter(
                    result_form=result_form,
                    entry_version=EntryVersion.FINAL,
                    result_form__form_state=FormState.ARCHIVED,
                    active=True).all()
                votes = sum([r.votes for r in results])

                output = {
                    'ballot': result_form.ballot.number,
                    'barcode': barcode,
                    'order': candidate.order,
                    'name': candidate.full_name,
                    'votes': votes
                }

                w.writerow({
                    k: v.encode('utf8') if isinstance(v, basestring)
                    else v for k, v in output.items()})


def export_candidate_votes(output=None, save_barcodes=False):
    header = ['ballot number',
              'stations',
              'stations completed',
              'stations percent completed']

    max_candidates = 0
    for ballot in Ballot.objects.all():
        if ballot.candidates.count() > max_candidates:
            max_candidates = ballot.candidates.count()

    for i in xrange(1, max_candidates + 1):
        header.append('candidate %s name' % i)
        header.append('candidate %s votes' % i)

    complete_barcodes = []

    with open(OUTPUT_PATH, 'wb') as f:
        # BOM, Excel needs it to open UTF-8 file properly
        f.write(u'\ufeff'.encode('utf8'))
        w = csv.DictWriter(f, header)
        w.writeheader()

        for ballot in Ballot.objects.exclude(number=54):
            general_ballot = ballot
            forms = distinct_forms(ballot)
            final_forms = forms.filter(form_state=FormState.ARCHIVED)

            if not SPECIAL_BALLOTS or ballot.number in SPECIAL_BALLOTS:
                complete_barcodes.extend([r.barcode for r in final_forms])

            num_stations = forms.count()
            num_stations_completed = final_forms.count()

            percent_complete = round(
                100 * num_stations_completed / num_stations, 3)

            output = OrderedDict({
                'ballot number': ballot.number,
                'stations': num_stations,
                'stations completed': num_stations_completed,
                'stations percent completed': percent_complete})

            candidates_to_votes = {}
            num_results_ary = []

            for candidate in ballot.candidates.all():
                num_results, votes = get_votes(candidate)
                candidates_to_votes[candidate.full_name] = votes
                num_results_ary.append(num_results)

            assert len(set(num_results_ary)) <= 1

            for num_results in num_results_ary:
                if num_stations_completed != num_results:
                    print ('[WARNING] Number stations complete (%s) not '
                           'equal to num_results (%s) for ballot %s (general'
                           ' ballot %s)' % (
                               num_stations_completed, num_results,
                               ballot.number, general_ballot.number))
                    output['stations completed'] = num_results

            candidates_to_votes = OrderedDict((sorted(
                candidates_to_votes.items(), key=lambda t: t[1],
                reverse=True)))

            for i, item in enumerate(candidates_to_votes.items()):
                candidate, votes = item

                output['candidate %s name' % (i + 1)] = candidate
                output['candidate %s votes' % (i + 1)] = votes

            w.writerow({k: v.encode('utf8') if isinstance(v, basestring)
                        else v for k, v in output.items()})

        if save_barcodes:
            save_barcode_results(complete_barcodes)


def get_result_export_response(report):
    filename = 'not_found.csv'
    path = None
    if report == 'formresults':
        filename = 'form_results.csv'
        export_candidate_votes(save_barcodes=True)
        path = RESULTS_PATH
    elif report == 'candidates':
        filename = 'candidates_votes.csv'
        export_candidate_votes()
        path = OUTPUT_PATH
    response = HttpResponse(content_type='text/csv')
    response['Content-Desposition'] = 'attachment; filename=%s' % filename

    if path:
        with open(path, 'rb') as f:
            response.write(f.read())
    else:
        response.write(_(u"Report not found."))
        response.status_code = 404
    return response