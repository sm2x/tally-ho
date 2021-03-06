from django.core.exceptions import PermissionDenied, SuspiciousOperation
from django.contrib.auth.models import AnonymousUser
from django.urls import reverse
from django.test import RequestFactory

from tally_ho.apps.tally.views import quality_control as views
from tally_ho.apps.tally.models.quality_control import QualityControl
from tally_ho.apps.tally.models.quarantine_check import QuarantineCheck
from tally_ho.apps.tally.models.result_form import ResultForm
from tally_ho.libs.models.enums.form_state import FormState
from tally_ho.libs.permissions import groups
from tally_ho.libs.tests.test_base import (
    create_candidates,
    create_reconciliation_form,
    create_recon_forms,
    create_result_form,
    create_center,
    create_station,
    create_audit,
    create_tally,
    create_ballot,
    TestBase,
)
from tally_ho.libs.verify.quarantine_checks import create_quarantine_checks


def create_quality_control(result_form, user):
    return QualityControl.objects.create(result_form=result_form,
                                         user=user)


class TestQualityControl(TestBase):
    def setUp(self):
        self.factory = RequestFactory()
        self._create_permission_groups()

    def _common_view_tests(self, view):
        request = self.factory.get('/')
        request.user = AnonymousUser()
        response = view(request)
        self.assertEqual(response.status_code, 302)
        self.assertEqual('/accounts/login/?next=/', response['location'])
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        request.user = self.user
        with self.assertRaises(PermissionDenied):
            view(request, tally_id=tally.pk)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        response = view(request, tally_id=tally.pk)
        response.render()
        self.assertIn(b'/accounts/logout/', response.content)
        return response

    def test_quality_control_get(self):
        response = self._common_view_tests(views.QualityControlView.as_view())
        self.assertContains(response, 'Quality Control')
        self.assertIn(b'<form id="result_form"', response.content)

    def test_quality_control_post(self):
        barcode = '123456789'
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        create_result_form(barcode,
                           tally=tally,
                           form_state=FormState.QUALITY_CONTROL)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.QualityControlView.as_view()
        data = {
            'barcode': barcode,
            'barcode_copy': barcode,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data=data)
        request.user = self.user
        request.session = {}
        response = view(request, tally_id=tally.pk)
        self.assertEqual(response.status_code, 302)
        self.assertIn('quality-control/dashboard',
                      response['location'])
        result_form = ResultForm.objects.get(barcode=barcode)
        self.assertEqual(result_form.form_state, FormState.QUALITY_CONTROL)
        self.assertEqual(result_form.qualitycontrol.user, self.user)

    def test_dashboard_abort_post(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        barcode = '123456789'
        create_result_form(barcode,
                           tally=tally,
                           form_state=FormState.QUALITY_CONTROL)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        result_form = ResultForm.objects.get(barcode=barcode)
        create_quality_control(result_form, self.user)
        view = views.QualityControlDashboardView.as_view()
        data = {
            'result_form': result_form.pk,
            'abort': 1,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data=data)
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)
        quality_control = result_form.qualitycontrol_set.all()[0]

        self.assertEqual(quality_control.active, False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('quality-control/home',
                      response['location'])
        self.assertEqual(request.session, {})

    def test_dashboard_incorrect_post_when_form_marked_for_release(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        barcode = '123456789'
        ballot = create_ballot(available_for_release=True)
        create_result_form(barcode,
                           ballot=ballot,
                           tally=tally,
                           form_state=FormState.QUALITY_CONTROL)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        result_form = ResultForm.objects.get(barcode=barcode)
        create_quality_control(result_form, self.user)
        view = views.QualityControlDashboardView.as_view()
        data = {
            'result_form': result_form.pk,
            'incorrect': 1,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data=data)
        request.user = self.user
        quality_control = result_form.qualitycontrol_set.all()[0]
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)

        self.assertTrue(quality_control.active)
        self.assertEqual(response.status_code, 302)
        self.assertIn('quality-control/confirm-reject',
                      response['location'])

    def test_dashboard_incorrect_post_when_form_not_marked_for_release(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        barcode = '123456789'
        create_result_form(barcode,
                           tally=tally,
                           form_state=FormState.QUALITY_CONTROL)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        result_form = ResultForm.objects.get(barcode=barcode)
        create_quality_control(result_form, self.user)
        view = views.QualityControlDashboardView.as_view()
        data = {
            'result_form': result_form.pk,
            'incorrect': 1,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data=data)
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)

        self.assertEqual(response.status_code, 302)
        self.assertIn('quality-control/reject',
                      response['location'])
        quality_control = result_form.qualitycontrol_set.all()[0]
        self.assertFalse(quality_control.active)
        self.assertEqual(request.session, {})

    def test_dashboard_submit_post(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        barcode = '123456789'
        create_result_form(barcode,
                           tally=tally,
                           form_state=FormState.QUALITY_CONTROL)
        result_form = ResultForm.objects.get(barcode=barcode)
        quality_control = create_quality_control(result_form, self.user)
        quality_control.passed_general = False
        quality_control.passed_reconciliation = False
        quality_control.passed_women = False
        quality_control.save()

        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.QualityControlDashboardView.as_view()
        data = {
            'result_form': result_form.pk,
            'correct': 1,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data=data)
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)
        result_form = ResultForm.objects.get(pk=result_form.pk)

        self.assertEqual(response.status_code, 302)
        self.assertIn('quality-control/print',
                      response['location'])
        quality_control = result_form.qualitycontrol
        self.assertTrue(quality_control.passed_general)
        self.assertTrue(quality_control.passed_reconciliation)
        self.assertTrue(quality_control.passed_women)
        self.assertEqual(result_form.form_state, FormState.QUALITY_CONTROL)

    def test_dashboard_get_double_recon(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        barcode = '123456789'
        center = create_center(tally=tally)
        station = create_station(center=center)
        result_form = create_result_form(barcode,
                                         center=center,
                                         station_number=station.station_number,
                                         tally=tally,
                                         form_state=FormState.QUALITY_CONTROL)
        create_reconciliation_form(result_form, self.user)
        create_reconciliation_form(result_form, self.user)
        create_candidates(result_form, self.user)
        create_quality_control(result_form, self.user)

        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.QualityControlDashboardView.as_view()
        request = self.factory.get('/')
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'General Results Section')
        self.assertContains(response, 'Cancel')

    def test_dashboard_get_double_recon_raise(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        barcode = '123456789'
        center = create_center(tally=tally)
        station = create_station(center=center)
        result_form = create_result_form(barcode,
                                         center=center,
                                         station_number=station.station_number,
                                         tally=tally,
                                         form_state=FormState.QUALITY_CONTROL)
        create_reconciliation_form(result_form, self.user)
        create_reconciliation_form(result_form, self.user,
                                   ballot_number_from=2)
        create_candidates(result_form, self.user)
        create_quality_control(result_form, self.user)

        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.QualityControlDashboardView.as_view()
        request = self.factory.get('/')
        request.user = self.user
        request.session = {'result_form': result_form.pk}

        with self.assertRaises(SuspiciousOperation):
            view(request, tally_id=tally.pk)

    def test_dashboard_get(self):
        barcode = '123456789'
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        center = create_center(tally=tally)
        station = create_station(center=center)
        create_result_form(barcode,
                           center=center,
                           station_number=station.station_number,
                           tally=tally,
                           form_state=FormState.QUALITY_CONTROL)
        result_form = ResultForm.objects.get(barcode=barcode)
        create_candidates(result_form, self.user)
        create_quality_control(result_form, self.user)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.QualityControlDashboardView.as_view()
        request = self.factory.get('/')
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)

        self.assertEqual(response.status_code, 200)
        # gender has been removed
        # self.assertContains(response, str(result_form.gender_name))
        self.assertContains(response, 'General Results Section')
        self.assertNotContains(response, 'Reconciliation')
        self.assertContains(response, 'Cancel')

    def test_confirm_form_reset_view_post(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        barcode = '123456789'
        ballot = create_ballot(available_for_release=True)
        create_result_form(barcode,
                           tally=tally,
                           ballot=ballot,
                           form_state=FormState.QUALITY_CONTROL)
        result_form = ResultForm.objects.get(barcode=barcode)
        create_quality_control(result_form, self.user)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.ConfirmFormResetView.as_view()
        reject_reason = 'Form Incorrect'
        data = {
            'reject_reason': reject_reason
        }
        request = self.factory.post('/', data=data)
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)
        result_form = ResultForm.objects.get(pk=result_form.pk)
        quality_control = result_form.qualitycontrol_set.all()[0]

        self.assertEqual(response.status_code, 302)
        self.assertIn('quality-control/reject',
                      response['location'])
        self.assertEqual(request.session, {})
        self.assertEqual(result_form.form_state, FormState.DATA_ENTRY_1)
        self.assertEqual(result_form.rejected_count, 1)
        self.assertEqual(result_form.reject_reason, reject_reason)
        self.assertFalse(quality_control.active)
        self.assertFalse(quality_control.passed_reconciliation)

    def test_reconciliation_get(self):
        barcode = '123456789'
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        create_result_form(barcode,
                           form_state=FormState.QUALITY_CONTROL,
                           tally=tally)
        result_form = ResultForm.objects.get(barcode=barcode)
        create_reconciliation_form(result_form, self.user)

        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.QualityControlDashboardView.as_view()
        request = self.factory.get('/')
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reconciliation')
        self.assertContains(response, 'Total number of the sorted and counted')

    def test_reconciliation_post_correct(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        barcode = '123456789'
        create_result_form(barcode,
                           tally=tally,
                           form_state=FormState.QUALITY_CONTROL)
        result_form = ResultForm.objects.get(barcode=barcode)
        create_quality_control(result_form, self.user)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.QualityControlDashboardView.as_view()
        data = {
            'result_form': result_form.pk,
            'correct': 1,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data=data)
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)
        result_form.reload()

        self.assertEqual(response.status_code, 302)
        self.assertIn('quality-control/print',
                      response['location'])
        quality_control = QualityControl.objects.get(
            pk=result_form.qualitycontrol.pk)
        self.assertEqual(result_form.form_state, FormState.QUALITY_CONTROL)
        self.assertTrue(quality_control.passed_reconciliation)

    def test_reconciliation_post_incorrect_ballot_released(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        barcode = '123456789'
        ballot = create_ballot(available_for_release=True)
        create_result_form(barcode,
                           tally=tally,
                           ballot=ballot,
                           form_state=FormState.QUALITY_CONTROL)
        result_form = ResultForm.objects.get(barcode=barcode)
        create_recon_forms(result_form, self.user)
        create_candidates(result_form, self.user)
        create_quality_control(result_form, self.user)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.QualityControlDashboardView.as_view()
        data = {
            'result_form': result_form.pk,
            'incorrect': 1,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data=data)
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)
        self.assertEqual(response.status_code, 302)
        self.assertIn('quality-control/confirm-reject',
                      response['location'])
        result_form = ResultForm.objects.get(pk=result_form.pk)
        quality_control = result_form.qualitycontrol_set.all()[0]
        self.assertTrue(quality_control.active)
        self.assertEqual(result_form.form_state, FormState.QUALITY_CONTROL)
        self.assertEqual(result_form.rejected_count, 0)

    def test_reconciliation_post_incorrect_ballot_not_released(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        barcode = '123456789'
        create_result_form(barcode,
                           tally=tally,
                           form_state=FormState.QUALITY_CONTROL)
        result_form = ResultForm.objects.get(barcode=barcode)
        create_recon_forms(result_form, self.user)
        create_candidates(result_form, self.user)
        create_quality_control(result_form, self.user)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.QualityControlDashboardView.as_view()
        data = {
            'result_form': result_form.pk,
            'incorrect': 1,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data=data)
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)
        self.assertEqual(response.status_code, 302)
        self.assertIn('quality-control/reject',
                      response['location'])
        self.assertEqual(result_form.rejected_count, 0)
        result_form = ResultForm.objects.get(pk=result_form.pk)
        quality_control = result_form.qualitycontrol_set.all()[0]

        results = result_form.results.all()
        self.assertTrue(len(results) > 0)

        for result in results:
            self.assertEqual(result.active, False)

        recon_forms = result_form.reconciliationform_set.all()
        self.assertTrue(len(recon_forms) > 0)

        for recon in recon_forms:
            self.assertEqual(recon.active, False)

        self.assertEqual(result_form.form_state, FormState.DATA_ENTRY_1)
        self.assertEqual(result_form.rejected_count, 1)
        self.assertEqual(quality_control.active, False)
        self.assertEqual(quality_control.passed_reconciliation, False)

    def test_reconciliation_post_abort(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        barcode = '123456789'
        create_result_form(barcode,
                           tally=tally,
                           form_state=FormState.QUALITY_CONTROL)
        result_form = ResultForm.objects.get(barcode=barcode)
        create_quality_control(result_form, self.user)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.QualityControlDashboardView.as_view()
        data = {
            'result_form': result_form.pk,
            'abort': 1,
            'tally_id': tally.id,
        }
        request = self.factory.post('/', data=data)
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)
        self.assertEqual(response.status_code, 302)
        self.assertIn('quality-control/home',
                      response['location'])
        quality_control = result_form.qualitycontrol_set.all()[0]
        self.assertEqual(quality_control.active, False)

    def test_general_get(self):
        barcode = '123456789'
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        center = create_center(tally=tally)
        station = create_station(center=center)
        create_result_form(barcode,
                           center=center,
                           station_number=station.station_number,
                           tally=tally,
                           form_state=FormState.QUALITY_CONTROL)
        result_form = ResultForm.objects.get(barcode=barcode)
        name = 'the candidate name'
        women_name = 'women candidate name'
        votes = 123

        create_candidates(result_form, self.user, name, votes, women_name)

        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.QualityControlDashboardView.as_view()
        request = self.factory.get('/')
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)
        response.render()
        self.assertEqual(response.status_code, 200)
        # gender has been removed
        # self.assertContains(response, str(result_form.gender_name))
        self.assertContains(response, 'General')
        self.assertContains(response, name)
        self.assertContains(response, women_name)
        self.assertContains(response, str(votes))

    def test_general_post_correct(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        barcode = '123456789'
        result_form = create_result_form(barcode,
                                         tally=tally,
                                         form_state=FormState.QUALITY_CONTROL)
        create_quality_control(result_form, self.user)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.QualityControlDashboardView.as_view()
        data = {
            'result_form': result_form.pk,
            'correct': 1,
            'tally_id': tally.id,
        }
        request = self.factory.post('/', data=data)
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)
        result_form.reload()

        self.assertEqual(response.status_code, 302)
        self.assertIn('quality-control/print',
                      response['location'])
        quality_control = QualityControl.objects.get(
            pk=result_form.qualitycontrol.pk)
        self.assertEqual(result_form.form_state, FormState.QUALITY_CONTROL)
        self.assertTrue(quality_control.passed_general)

    def test_general_post_incorrect_ballot_released(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        barcode = '123456789'
        ballot = create_ballot(available_for_release=True)
        create_result_form(barcode,
                           tally=tally,
                           ballot=ballot,
                           form_state=FormState.QUALITY_CONTROL)
        result_form = ResultForm.objects.get(barcode=barcode)
        create_quality_control(result_form, self.user)
        create_candidates(result_form, self.user)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.QualityControlDashboardView.as_view()
        data = {
            'result_form': result_form.pk,
            'incorrect': 1,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data=data)
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)
        self.assertEqual(response.status_code, 302)
        self.assertIn('quality-control/confirm-reject',
                      response['location'])
        result_form = ResultForm.objects.get(pk=result_form.pk)
        quality_control = result_form.qualitycontrol_set.all()[0]
        self.assertTrue(quality_control.active)
        self.assertEqual(result_form.form_state, FormState.QUALITY_CONTROL)
        self.assertEqual(result_form.rejected_count, 0)

    def test_general_post_incorrect_ballot_not_released(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        barcode = '123456789'
        create_result_form(barcode,
                           tally=tally,
                           form_state=FormState.QUALITY_CONTROL)
        result_form = ResultForm.objects.get(barcode=barcode)
        create_quality_control(result_form, self.user)
        create_candidates(result_form, self.user)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.QualityControlDashboardView.as_view()
        data = {
            'result_form': result_form.pk,
            'incorrect': 1,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data=data)
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)
        self.assertEqual(response.status_code, 302)
        self.assertIn('quality-control/reject',
                      response['location'])
        self.assertEqual(result_form.rejected_count, 0)
        result_form = ResultForm.objects.get(pk=result_form.pk)
        quality_control = result_form.qualitycontrol_set.all()[0]

        results = result_form.results.all()
        self.assertTrue(len(results) > 0)

        for result in results:
            self.assertEqual(result.active, False)

        self.assertEqual(result_form.form_state, FormState.DATA_ENTRY_1)
        self.assertEqual(result_form.rejected_count, 1)
        self.assertEqual(quality_control.active, False)
        self.assertEqual(quality_control.passed_general, False)

    def test_general_post_abort(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        barcode = '123456789'
        create_result_form(barcode,
                           tally=tally,
                           form_state=FormState.QUALITY_CONTROL)
        result_form = ResultForm.objects.get(barcode=barcode)
        create_quality_control(result_form, self.user)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.QualityControlDashboardView.as_view()
        data = {
            'result_form': result_form.pk,
            'abort': 1,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data=data)
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)
        self.assertEqual(response.status_code, 302)
        self.assertIn('quality-control/home',
                      response['location'])
        quality_control = result_form.qualitycontrol_set.all()[0]
        self.assertEqual(quality_control.active, False)

    def test_women_get(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        barcode = '123456789'
        center = create_center()
        station = create_station(center=center)
        create_result_form(barcode,
                           center=center,
                           station_number=station.station_number,
                           tally=tally,
                           form_state=FormState.QUALITY_CONTROL)
        result_form = ResultForm.objects.get(barcode=barcode)
        name = 'general candidate name'
        women_name = 'women candidate name'
        votes = 123

        create_candidates(result_form, self.user, name, votes, women_name)

        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.QualityControlDashboardView.as_view()
        request = self.factory.get('/')
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)
        response.render()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Women')
        self.assertContains(response, women_name)
        self.assertContains(response, name)
        self.assertContains(response, str(votes))

    def test_women_post_correct(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        barcode = '123456789'
        create_result_form(barcode,
                           tally=tally,
                           form_state=FormState.QUALITY_CONTROL)
        result_form = ResultForm.objects.get(barcode=barcode)
        create_quality_control(result_form, self.user)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.QualityControlDashboardView.as_view()
        data = {
            'result_form': result_form.pk,
            'correct': 1,
            'tally_id': tally.pk
        }
        request = self.factory.post('/', data=data)
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)
        result_form.reload()

        self.assertEqual(response.status_code, 302)
        self.assertIn('quality-control/print',
                      response['location'])
        quality_control = result_form.qualitycontrol_set.all()[0]
        self.assertEqual(result_form.form_state, FormState.QUALITY_CONTROL)
        self.assertTrue(quality_control.passed_women)

    def test_women_post_incorrect_ballot_released(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        barcode = '123456789'
        ballot = create_ballot(available_for_release=True)
        create_result_form(barcode,
                           tally=tally,
                           ballot=ballot,
                           form_state=FormState.QUALITY_CONTROL)
        result_form = ResultForm.objects.get(barcode=barcode)
        create_quality_control(result_form, self.user)
        create_candidates(result_form, self.user)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.QualityControlDashboardView.as_view()
        data = {
            'result_form': result_form.pk,
            'incorrect': 1,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data=data)
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)
        self.assertEqual(response.status_code, 302)
        self.assertIn('quality-control/confirm-reject',
                      response['location'])
        result_form = ResultForm.objects.get(pk=result_form.pk)
        quality_control = result_form.qualitycontrol_set.all()[0]
        self.assertTrue(quality_control.active)
        self.assertEqual(result_form.form_state, FormState.QUALITY_CONTROL)
        self.assertEqual(result_form.rejected_count, 0)

    def test_women_post_incorrect_ballot_not_released(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        barcode = '123456789'
        create_result_form(barcode,
                           tally=tally,
                           form_state=FormState.QUALITY_CONTROL)
        result_form = ResultForm.objects.get(barcode=barcode)
        create_quality_control(result_form, self.user)
        create_candidates(result_form, self.user)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.QualityControlDashboardView.as_view()
        data = {
            'result_form': result_form.pk,
            'incorrect': 1,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data=data)
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)
        self.assertEqual(response.status_code, 302)
        self.assertIn('quality-control/reject',
                      response['location'])
        self.assertEqual(result_form.rejected_count, 0)
        result_form = ResultForm.objects.get(pk=result_form.pk)
        quality_control = result_form.qualitycontrol_set.all()[0]

        results = result_form.results.all()
        self.assertTrue(len(results) > 0)

        for result in results:
            self.assertEqual(result.active, False)

        self.assertEqual(result_form.form_state, FormState.DATA_ENTRY_1)
        self.assertEqual(result_form.rejected_count, 1)
        self.assertEqual(quality_control.active, False)
        self.assertEqual(quality_control.passed_women, False)

    def test_women_post_abort(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        barcode = '123456789'
        create_result_form(barcode,
                           tally=tally,
                           form_state=FormState.QUALITY_CONTROL)
        result_form = ResultForm.objects.get(barcode=barcode)
        create_quality_control(result_form, self.user)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.QualityControlDashboardView.as_view()
        data = {
            'result_form': result_form.pk,
            'abort': 1,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data=data)
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)
        self.assertEqual(response.status_code, 302)
        self.assertIn('quality-control/home',
                      response['location'])
        quality_control = result_form.qualitycontrol_set.all()[0]
        self.assertEqual(quality_control.active, False)

    def test_quality_control_post_quarantine_pass_with_zero_diff(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        center = create_center()
        create_station(center)
        create_quarantine_checks()
        result_form = create_result_form(
            form_state=FormState.QUALITY_CONTROL,
            center=center,
            tally=tally,
            station_number=1)
        recon_form = create_reconciliation_form(
            result_form, self.user, number_unstamped_ballots=0)
        create_quality_control(result_form, self.user)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.QualityControlDashboardView.as_view()
        data = {
            'correct': 1,
            'result_form': result_form.pk,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data=data)
        request.session = {'result_form': result_form.pk}
        request.user = self.user
        response = view(request, tally_id=tally.pk)
        result_form.reload()

        self.assertEqual(result_form.num_votes,
                         recon_form.number_ballots_expected)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(result_form.form_state, FormState.AUDIT)
        self.assertIsNone(result_form.audit)
        self.assertEqual(result_form.audited_count, 0)
        self.assertIn('quality-control/print', response['location'])

    def test_quality_control_post_quarantine_pass_below_tolerance(self):
        center = create_center()
        create_station(center)
        create_quarantine_checks()
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        result_form = create_result_form(
            tally=tally,
            form_state=FormState.QUALITY_CONTROL,
            center=center, station_number=1)
        recon_form = create_reconciliation_form(
            result_form, self.user, number_ballots_inside_box=21,
            number_unstamped_ballots=0)
        create_quality_control(result_form, self.user)
        create_candidates(result_form, self.user, votes=1, num_results=10)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.QualityControlDashboardView.as_view()
        data = {
            'correct': 1,
            'result_form': result_form.pk,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data=data)
        request.session = {'result_form': result_form.pk}
        request.user = self.user
        response = view(request, tally_id=tally.pk)
        result_form.reload()

        self.assertEqual(result_form.num_votes,
                         recon_form.number_ballots_expected)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(result_form.form_state, FormState.AUDIT)
        self.assertTrue(result_form.audit)
        self.assertEqual(result_form.audit.quarantine_checks.count(), 1)
        self.assertEqual(
            result_form.audit.quarantine_checks.all()[0].name[:9], 'Trigger 1')
        self.assertEqual(result_form.audited_count, 1)
        self.assertIn('quality-control/print', response['location'])

    def test_quality_control_post_quarantine(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        center = create_center()
        create_station(center)
        create_quarantine_checks()
        result_form = create_result_form(
            form_state=FormState.QUALITY_CONTROL,
            tally=tally,
            center=center,
            station_number=1)
        create_reconciliation_form(
            result_form, self.user, number_unstamped_ballots=1000)
        create_quality_control(result_form, self.user)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.QualityControlDashboardView.as_view()
        data = {
            'correct': 1,
            'result_form': result_form.pk,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data=data)
        request.session = {'result_form': result_form.pk}
        request.user = self.user
        response = view(request, tally_id=tally.pk)
        result_form.reload()

        self.assertEqual(response.status_code, 302)
        self.assertTrue(result_form.form_state, FormState.AUDIT)
        self.assertTrue(result_form.audit)
        self.assertEqual(result_form.audit.quarantine_checks.count(), 2)
        self.assertEqual(result_form.audit.user, self.user)
        self.assertEqual(result_form.audited_count, 1)
        self.assertIn('quality-control/print', response['location'])

    def test_print_success_get(self):
        self._create_and_login_user()
        code = '12345'
        station_number = 1
        center = create_center(code)
        create_station(center)
        result_form = create_result_form(form_state=FormState.QUALITY_CONTROL,
                                         center=center,
                                         station_number=station_number)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.PrintView.as_view()
        request = self.factory.get('/')
        request.session = {'result_form': result_form.pk}
        request.user = self.user
        response = view(request)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Successful Archive')

    def test_print_quarantine_get(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        code = '12345'
        station_number = 1
        center = create_center(code, tally=tally)
        create_station(center)
        result_form = create_result_form(form_state=FormState.QUALITY_CONTROL,
                                         center=center,
                                         tally=tally,
                                         station_number=station_number)
        quarantine_check = QuarantineCheck.objects.create(
            user=self.user,
            name='1',
            method='1',
            value=1)
        audit = create_audit(result_form, self.user)
        audit.quarantine_checks.add(quarantine_check)

        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.PrintView.as_view()
        request = self.factory.get('/')
        request.session = {'result_form': result_form.pk}
        request.user = self.user
        response = view(request, tally_id=tally.pk)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Quarantined')

    def test_print_post(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)

        result_form = create_result_form(form_state=FormState.QUALITY_CONTROL)
        view = views.PrintView.as_view()
        data = {
            'result_form': result_form.pk,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data=data)
        request.session = data
        request.user = self.user
        response = view(request, tally_id=tally.pk)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/quality-control/success', response['location'])

        result_form = ResultForm.objects.get(pk=result_form.pk)
        self.assertEqual(result_form.form_state, FormState.ARCHIVED)

    def test_confirmation_get(self):
        self._create_and_login_user()
        tally = create_tally()
        tally.users.add(self.user)
        result_form = create_result_form(tally=tally,
                                         form_state=FormState.ARCHIVED)
        self._add_user_to_group(self.user, groups.QUALITY_CONTROL_CLERK)
        view = views.ConfirmationView.as_view()
        request = self.factory.get('/')
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Archiving')
        self.assertContains(
            response,
            reverse('quality-control', kwargs={'tally_id': tally.pk}))
        self.assertEqual(request.session.get('result_form'), None)
