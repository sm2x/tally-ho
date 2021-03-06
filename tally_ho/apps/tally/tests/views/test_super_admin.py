import os
import shutil
from django.core.exceptions import SuspiciousOperation
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.messages.storage import default_storage
from django.conf import settings
from django.test import RequestFactory

from tally_ho.apps.tally.models.ballot import Ballot
from tally_ho.apps.tally.models.result import Result
from tally_ho.apps.tally.models.station import Station
from tally_ho.apps.tally.models.sub_constituency import SubConstituency
from tally_ho.apps.tally.models.result_form import ResultForm
from tally_ho.apps.tally.forms.create_result_form import CreateResultForm
from tally_ho.apps.tally.forms.edit_result_form import EditResultForm
from tally_ho.apps.tally.views import super_admin as views
from tally_ho.libs.models.enums.entry_version import EntryVersion
from tally_ho.libs.models.enums.form_state import FormState
from tally_ho.libs.models.enums.gender import Gender
from tally_ho.libs.models.enums.race_type import RaceType
from tally_ho.libs.permissions import groups
from tally_ho.libs.tests.test_base import (
    configure_messages,
    create_audit,
    create_ballot,
    create_candidates,
    create_reconciliation_form,
    create_result_form,
    create_result,
    create_center,
    create_station,
    create_tally,
    TestBase,
)


class TestSuperAdmin(TestBase):
    def setUp(self):
        self.factory = RequestFactory()
        self._create_permission_groups()
        self._create_and_login_user()
        self._add_user_to_group(self.user, groups.SUPER_ADMINISTRATOR)

    def test_form_action_view_post_invalid_audit(self):
        tally = create_tally()
        tally.users.add(self.user)
        result_form = create_result_form(form_state=FormState.AUDIT,
                                         tally=tally)
        request = self._get_request()
        view = views.FormActionView.as_view()
        data = {'result_form': result_form.pk}
        request = self.factory.post('/', data=data)
        request.user = self.user
        request.session = {}

        with self.assertRaises(SuspiciousOperation):
            view(request, tally_id=tally.pk)

    def test_form_action_view_post_review_audit(self):
        tally = create_tally()
        tally.users.add(self.user)
        result_form = create_result_form(form_state=FormState.AUDIT,
                                         tally=tally)
        request = self._get_request()
        view = views.FormActionView.as_view()
        data = {'result_form': result_form.pk,
                'review': 1}
        request = self.factory.post('/', data=data)
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/audit/review', response['Location'])

    def test_form_action_view_post_confirm_audit(self):
        tally = create_tally()
        tally.users.add(self.user)
        result_form = create_result_form(form_state=FormState.AUDIT,
                                         tally=tally)
        create_reconciliation_form(result_form, self.user)
        create_reconciliation_form(result_form, self.user)
        create_candidates(result_form, self.user)
        audit = create_audit(result_form, self.user)

        request = self._get_request()
        view = views.FormActionView.as_view()
        data = {'result_form': result_form.pk,
                'confirm': 1}
        request = self.factory.post('/', data=data)
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk)

        audit.reload()
        result_form.reload()
        self.assertFalse(audit.active)
        self.assertEqual(result_form.form_state, FormState.DATA_ENTRY_1)
        self.assertTrue(result_form.skip_quarantine_checks)

        self.assertEqual(len(result_form.results.all()), 20)
        self.assertEqual(len(result_form.reconciliationform_set.all()),
                         2)

        for result in result_form.results.all():
            self.assertFalse(result.active)

        for result in result_form.reconciliationform_set.all():
            self.assertFalse(result.active)

        self.assertEqual(response.status_code, 302)
        self.assertIn('/super-administrator/form-action-list',
                      response['Location'])

    def test_result_export_view(self):
        tally = create_tally()
        tally.users.add(self.user)
        view = views.ResultExportView.as_view()
        request = self.factory.get('/')
        request.user = self.user
        response = view(request, tally_id=tally.pk)
        self.assertContains(response, "Downloads")

    def test_remove_center_get(self):
        tally = create_tally()
        tally.users.add(self.user)
        view = views.RemoveCenterView.as_view()
        request = self.factory.get('/')
        request.user = self.user
        response = view(request, tally_id=tally.pk)
        self.assertContains(response, 'name="center_number"')
        self.assertContains(response, '<form name="remove-center-form"')

    def test_remove_center_post_invalid(self):
        tally = create_tally()
        tally.users.add(self.user)
        center = create_center(tally=tally)
        view = views.RemoveCenterView.as_view()
        data = {
            'center_number': center.code,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data)
        request.user = self.user
        response = view(request, tally_id=tally.pk)
        self.assertContains(response,
                            'Ensure this value has at least 5 character')

    def test_remove_center_post_valid(self):
        tally = create_tally()
        tally.users.add(self.user)
        center = create_center('12345', tally=tally)
        view = views.RemoveCenterView.as_view()
        data = {
            'center_number': center.code,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data)
        request.user = self.user
        request.session = {}
        request._messages = default_storage(request)
        response = view(request, tally_id=tally.pk)
        self.assertEqual(response.status_code, 302)
        # TODO this happens in RemoveCenterConfirmationView#delete
        # with self.assertRaises(Center.DoesNotExist):
        #     Center.objects.get(code=center.code)

    def test_remove_center_post_result_exists(self):
        tally = create_tally()
        tally.users.add(self.user)
        center = create_center('12345', tally=tally)
        result_form = create_result_form(center=center,
                                         form_state=FormState.AUDIT)
        create_reconciliation_form(result_form, self.user)
        create_reconciliation_form(result_form, self.user)
        create_candidates(result_form, self.user)
        self.assertTrue(Result.objects.filter().count() > 0)

        view = views.RemoveCenterView.as_view()
        data = {
            'center_number': center.code,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data)
        request.user = self.user
        response = view(request, tally_id=tally.pk)
        self.assertContains(response, u"Results exist for barcodes")
        self.assertContains(response, result_form.barcode)

    def test_remove_center_link(self):
        tally = create_tally()
        tally.users.add(self.user)
        view = views.DashboardView.as_view()
        request = self.factory.get('/')
        request.user = self.user
        response = view(request, tally_id=tally.pk)
        self.assertContains(response, "Remove a Center</a>")

    def test_remove_station_get(self):
        tally = create_tally()
        tally.users.add(self.user)
        view = views.RemoveStationView.as_view()
        request = self.factory.get('/')
        request.user = self.user
        response = view(request, tally_id=tally.pk)
        self.assertContains(response, 'name="center_number"')
        self.assertContains(response, 'name="station_number"')
        self.assertContains(response, '<form name="remove-station-form"')

    def test_remove_station_post_invalid(self):
        station = 1
        tally = create_tally()
        tally.users.add(self.user)
        center = create_center(tally=tally)
        view = views.RemoveStationView.as_view()
        data = {
            'center_number': center.code,
            'station_number': station,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data)
        request.user = self.user
        response = view(request, tally_id=tally.pk)
        self.assertContains(response,
                            'Ensure this value has at least 5 character')

    def test_remove_station_post_valid(self):
        tally = create_tally()
        tally.users.add(self.user)
        center = create_center('12345', tally=tally)
        station = create_station(center)
        self.assertEqual(
            Station.objects.get(center__code=center.code,
                                station_number=station.station_number),
            station
        )
        view = views.RemoveStationView.as_view()
        data = {
            'center_number': center.code,
            'station_number': station.station_number,
            'station_id': station.pk,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data)
        request.user = self.user
        request.session = {}
        request._messages = default_storage(request)
        response = view(request, tally_id=tally.pk)
        self.assertEqual(response.status_code, 302)
        # TODO this happens in RemoveStationConfirmationView#delete
        # with self.assertRaises(Station.DoesNotExist):
        #     Station.objects.get(center__code=center.code,
        #                         station_number=station.station_number)

    def test_remove_station_post_result_exists(self):
        tally = create_tally()
        tally.users.add(self.user)
        center = create_center('12345', tally=tally)
        station = create_station(center)
        result_form = create_result_form(center=center,
                                         form_state=FormState.AUDIT,
                                         station_number=station.station_number)
        create_reconciliation_form(result_form, self.user)
        create_reconciliation_form(result_form, self.user)
        create_candidates(result_form, self.user)
        self.assertTrue(Result.objects.filter().count() > 0)

        view = views.RemoveStationView.as_view()
        data = {
            'center_number': center.code,
            'station_number': station.station_number,
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data)
        request.user = self.user
        response = view(request, tally_id=tally.pk)
        self.assertContains(response, u"Results exist for barcodes")
        self.assertContains(response, result_form.barcode)

    def test_remove_station_link(self):
        tally = create_tally()
        tally.users.add(self.user)
        view = views.DashboardView.as_view()
        request = self.factory.get('/')
        request.user = self.user
        response = view(request, tally_id=tally.pk)
        self.assertContains(response, "Remove a Station</a>")

    def test_edit_station_get(self):
        tally = create_tally()
        tally.users.add(self.user)
        center = create_center('12345', tally=tally)
        station = create_station(center)
        view = views.EditStationView.as_view()
        request = self.factory.get('/')
        request.user = self.user
        response = view(
            request,
            station_id=station.pk,
            tally_id=tally.pk)
        self.assertContains(response, 'Edit Station')
        self.assertContains(response, '<td>%s</td>' % station.station_number)

    def test_edit_station_post(self):
        tally = create_tally()
        tally.users.add(self.user)
        center = create_center(tally=tally)
        station = create_station(center)
        view = views.EditStationView.as_view()
        data = {
            'center_code': center.code,
            'station_number': station.station_number,
            'tally_id': tally.pk,
            'gender': station.gender.value,
        }
        request = self.factory.post('/', data)
        request.user = self.user
        configure_messages(request)
        response = view(
            request,
            station_id=station.pk,
            tally_id=tally.pk)
        self.assertEqual(response.status_code, 302)

    def test_create_center(self):
        tally = create_tally()
        tally.users.add(self.user)
        view = views.CreateCenterView.as_view()
        data = {
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data)
        request.user = self.user
        configure_messages(request)
        response = view(
            request,
            tally_id=tally.pk)
        self.assertEqual(response.status_code, 200)

    def test_create_station(self):
        tally = create_tally()
        tally.users.add(self.user)
        view = views.CreateStationView.as_view()
        data = {
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data)
        request.user = self.user
        configure_messages(request)
        response = view(
            request,
            tally_id=tally.pk)
        self.assertEqual(response.status_code, 200)

    def test_disable_entity_view_post_station_invalid(self):
        tally = create_tally()
        tally.users.add(self.user)
        center = create_center(tally=tally)
        station = create_station(center)
        view = views.DisableEntityView.as_view()
        data = {
            'tally_id': tally.pk,
        }
        request = self.factory.post('/', data)
        request.user = self.user
        response = view(
            request,
            center_code=center.code,
            station_number=station.station_number,
            tally_id=tally.pk)
        self.assertContains(response,
                            'This field is required')

    def test_disable_entity_view_post_station(self):
        tally = create_tally()
        tally.users.add(self.user)
        center = create_center(tally=tally)
        station = create_station(center)
        comment_text = 'example comment text'
        view = views.DisableEntityView.as_view()
        data = {
            'center_code_input': center.code,
            'station_number_input': station.station_number,
            'tally_id': tally.pk,
            'comment_input': comment_text,
            'disable_reason': '2',
        }
        request = self.factory.post('/', data)
        request.user = self.user
        response = view(
            request,
            center_code=center.code,
            station_number=station.station_number,
            tally_id=tally.pk)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/data/center-list/%s/' % tally.pk, response['Location'])
        station.reload()
        self.assertEqual(station.disable_reason.value, 2)
        self.assertEqual(station.comments.all()[0].text, comment_text)

    def test_disable_entity_view_post_center(self):
        tally = create_tally()
        tally.users.add(self.user)
        center = create_center(tally=tally)
        station = create_station(center)
        comment_text = 'example comment text'
        view = views.DisableEntityView.as_view()
        data = {
            'center_code_input': center.code,
            'comment_input': comment_text,
            'tally_id': tally.pk,
            'disable_reason': '2',
        }
        request = self.factory.post('/', data)
        request.user = self.user
        response = view(
            request,
            center_code=center.code,
            station_number=station.station_number,
            tally_id=tally.pk)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/data/center-list/%s/' % tally.pk, response['Location'])
        center.reload()
        self.assertEqual(center.disable_reason.value, 2)
        self.assertEqual(center.comments.all()[0].text, comment_text)

    def test_disable_race_view_post(self):
        tally = create_tally()
        tally.users.add(self.user)
        ballot = create_ballot(tally=tally)
        comment_text = 'example comment text'
        view = views.DisableRaceView.as_view()
        data = {
            'race_id_input': ballot.pk,
            'comment_input': comment_text,
            'tally_id': tally.pk,
            'disable_reason': '2',
        }
        request = self.factory.post('/', data)
        request.user = self.user
        configure_messages(request)
        response = view(
            request,
            tally_id=tally.pk)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/data/races-list/%s/' % tally.pk, response['Location'])
        ballot.reload()
        self.assertEqual(ballot.disable_reason.value, 2)
        self.assertEqual(ballot.comments.all()[0].text, comment_text)

    def test_create_race_invalid_document_extension_error(self):
        tally = create_tally()
        tally.users.add(self.user)
        view = views.CreateRaceView.as_view()
        file_size = settings.MAX_FILE_UPLOAD_SIZE
        video = SimpleUploadedFile(
            "file.mp4", bytes(file_size), content_type="video/mp4")
        data = {
            'number': 1,
            'race_type': 0,
            'tally_id': tally.pk,
            'available_for_release': True,
            'document': video,
        }
        request = self.factory.post('/', data)
        request.user = self.user
        request.session = data
        configure_messages(request)
        response = view(
            request,
            tally_id=tally.pk)
        self.assertFalse(response.context_data['form'].is_valid())
        self.assertEqual(
            response.context_data['form'].errors['document'][0],
            str('File extention (.mp4) is not supported.'
                ' Allowed extensions are: .png, .jpg, .doc, .pdf.'))

    def test_create_race_invalid_document_size_error(self):
        tally = create_tally()
        tally.users.add(self.user)
        view = views.CreateRaceView.as_view()
        file_size = settings.MAX_FILE_UPLOAD_SIZE * 2
        image = SimpleUploadedFile(
            "image.jpg", bytes(file_size), content_type="image/jpeg")
        data = {
            'number': 1,
            'race_type': 0,
            'tally_id': tally.pk,
            'available_for_release': True,
            'document': image,
        }
        request = self.factory.post('/', data)
        request.user = self.user
        request.session = data
        configure_messages(request)
        response = view(
            request,
            tally_id=tally.pk)
        self.assertFalse(response.context_data['form'].is_valid())
        self.assertEqual(
            response.context_data['form'].errors['document'][0],
            str('File size must be under 10.0\xa0MB.'
                ' Current file size is 20.0\xa0MB.'))

    def test_create_race_view(self):
        tally = create_tally()
        tally.users.add(self.user)
        view = views.CreateRaceView.as_view()
        file_size = settings.MAX_FILE_UPLOAD_SIZE
        image_file_name = "image.jpg"
        image_file = SimpleUploadedFile(
            image_file_name, bytes(file_size), content_type="image/jpeg")
        data = {
            'number': 2,
            'race_type': 0,
            'tally_id': tally.pk,
            'available_for_release': True,
            'document': image_file,
        }
        request = self.factory.post('/', data)
        request.user = self.user
        request.session = data
        configure_messages(request)
        response = view(
            request,
            tally_id=tally.pk)
        self.assertEqual(response.status_code, 302)
        ballot = Ballot.objects.get(document__isnull=False)
        self.assertIn(image_file_name, ballot.document.path)
        shutil.rmtree(os.path.dirname(ballot.document.path))

    def test_edit_race_view_get(self):
        tally = create_tally()
        tally.users.add(self.user)
        ballot = create_ballot(tally)
        view = views.EditRaceView.as_view()
        request = self.factory.get('/')
        request.user = self.user
        response = view(
            request,
            id=ballot.pk,
            tally_id=tally.pk)
        self.assertContains(response, 'Edit Race')
        self.assertContains(response, 'value="%s"' % ballot.number)

    def test_edit_race_view_post(self):
        tally = create_tally()
        tally.users.add(self.user)
        file_size = settings.MAX_FILE_UPLOAD_SIZE
        pdf_file_name = "file.pdf"
        image_file_name = "image.jpg"
        pdf_file = SimpleUploadedFile(
            pdf_file_name, bytes(file_size), content_type="application/pdf")
        image_file = SimpleUploadedFile(
            image_file_name, bytes(file_size), content_type="image/jpeg")
        ballot = create_ballot(tally, document=pdf_file)
        comment_text = 'jndfjs fsgfd'
        view = views.EditRaceView.as_view()
        data = {
            'comment_input': comment_text,
            'number': ballot.number,
            'race_type': ballot.race_type.value,
            'available_for_release': True,
            'race_id': ballot.pk,
            'tally_id': tally.pk,
            'document': image_file,
        }
        request = self.factory.post('/', data)
        request.user = self.user
        configure_messages(request)
        response = view(
            request,
            id=ballot.pk,
            tally_id=tally.pk)
        self.assertEqual(response.status_code, 302)
        ballot.reload()
        ballot.refresh_from_db()

        # testing auto_delete_document signal was called
        self.assertNotIn(pdf_file_name, ballot.document.path)
        self.assertIn(image_file_name, ballot.document.path)
        self.assertEqual(ballot.available_for_release, True)
        self.assertEqual(ballot.comments.first().text, comment_text)
        shutil.rmtree(os.path.dirname(ballot.document.path))

    def test_form_duplicates_view_get(self):
        tally = create_tally()
        tally.users.add(self.user)
        view = views.FormDuplicatesView.as_view()
        request = self.factory.get('/')
        request.user = self.user
        response = view(
            request,
            tally_id=tally.pk)
        self.assertContains(response, 'Form Duplicates List')

    def test_edit_result_form_get(self):
        tally = create_tally()
        tally.users.add(self.user)
        code = '12345'
        station_number = 1
        center = create_center(code, tally=tally)
        result_form = create_result_form(form_state=FormState.UNSUBMITTED,
                                         center=center,
                                         tally=tally,
                                         station_number=station_number)
        view = views.EditResultFormView.as_view()
        request = self.factory.get('/')
        request.user = self.user
        response = view(
            request,
            form_id=result_form.pk,
            tally_id=tally.pk)
        self.assertContains(response, 'Edit Form')

    def test_create_result_form_mandatory_fields(self):
        form_data = {}
        form = CreateResultForm(form_data)
        self.assertIn("All fields are mandatory", form.errors['__all__'])
        self.assertFalse(form.is_valid())

    def test_create_result_form_ballot_not_active_error(self):
        tally = create_tally()
        tally.users.add(self.user)
        code = '12345'
        center = create_center(code, tally=tally)
        ballot = create_ballot(tally=tally, active=False)
        station = create_station(center)
        form_data = {'center': center.pk,
                     'station_number': station.station_number,
                     'tally': tally.pk,
                     'form_state': 9,
                     'ballot': ballot.pk,
                     'barcode': 12345,
                     'created_user': self.request.user.userprofile,
                     'gender': 1}
        form = CreateResultForm(form_data)
        self.assertIn("Race for ballot is disabled", form.errors['__all__'])
        self.assertFalse(form.is_valid())

    def test_create_result_form_center_not_active_error(self):
        tally = create_tally()
        tally.users.add(self.user)
        code = '12345'
        center = create_center(code, tally=tally, active=False)
        ballot = create_ballot(tally=tally)
        station = create_station(center)
        form_data = {'center': center.pk,
                     'station_number': station.station_number,
                     'tally': tally.pk,
                     'form_state': 9,
                     'ballot': ballot.pk,
                     'barcode': 12345,
                     'created_user': self.request.user.userprofile,
                     'gender': 1}
        form = CreateResultForm(form_data)
        self.assertIn("Selected center is disabled", form.errors['__all__'])
        self.assertFalse(form.is_valid())

    def test_create_result_form_station_not_active_error(self):
        tally = create_tally()
        tally.users.add(self.user)
        code = '12345'
        center = create_center(code, tally=tally)
        ballot = create_ballot(tally=tally)
        station = create_station(center, active=False)
        form_data = {'center': center.pk,
                     'station_number': station.station_number,
                     'tally': tally.pk,
                     'form_state': 9,
                     'ballot': ballot.pk,
                     'barcode': 12345,
                     'created_user': self.request.user.userprofile,
                     'gender': 1}
        form = CreateResultForm(form_data)
        self.assertIn("Selected station is disabled", form.errors['__all__'])
        self.assertFalse(form.is_valid())

    def test_create_result_form_station_does_not_exist_error(self):
        tally = create_tally()
        tally.users.add(self.user)
        code = '12345'
        station_number = 1
        center = create_center(code, tally=tally)
        ballot = create_ballot(tally=tally)
        form_data = {'center': center.pk,
                     'station_number': station_number,
                     'tally': tally.pk,
                     'form_state': 9,
                     'ballot': ballot.pk,
                     'barcode': 12345,
                     'created_user': self.request.user.userprofile,
                     'gender': 1}
        form = CreateResultForm(form_data)
        self.assertIn("Station does not exist for the selected center",
                      form.errors['__all__'])
        self.assertFalse(form.is_valid())

    def test_create_result_form_ballot_number_mis_match_error(self):
        tally = create_tally()
        tally.users.add(self.user)
        code = '12345'
        ballot = create_ballot(tally=tally, number=2)
        sc, _ = SubConstituency.objects.get_or_create(code=1, field_office='1')
        center = create_center(code,
                               tally=tally,
                               sub_constituency=sc)
        station = create_station(center)
        form_data = {'center': center.pk,
                     'station_number': station.station_number,
                     'tally': tally.pk,
                     'form_state': 9,
                     'ballot': ballot.pk,
                     'barcode': 12345,
                     'created_user': self.request.user.userprofile,
                     'gender': 1}
        form = CreateResultForm(form_data)
        self.assertIn("Ballot number do not match for center and station",
                      form.errors['__all__'])
        self.assertFalse(form.is_valid())

    def test_create_result_form_valid(self):
        tally = create_tally()
        tally.users.add(self.user)
        code = '12345'
        barcode = '12345'
        ballot = create_ballot(tally=tally)
        sc, _ = SubConstituency.objects.get_or_create(code=1, field_office='1')
        center = create_center(code,
                               tally=tally,
                               sub_constituency=sc)
        station = create_station(center)
        form_data = {'center': center.pk,
                     'station_number': station.station_number,
                     'tally': tally.pk,
                     'form_state': 9,
                     'ballot': ballot.pk,
                     'barcode': barcode,
                     'created_user': self.request.user.userprofile,
                     'gender': 1}
        form = CreateResultForm(form_data)
        self.assertTrue(form.is_valid())
        self.assertEqual(form.instance.barcode, barcode)
        form.save()
        self.assertEqual(
            ResultForm.objects.get(id=form.instance.id).barcode,
            barcode
        )

    def test_create_result_form_view(self):
        tally = create_tally()
        tally.users.add(self.user)
        code = '12345'
        station_number = 1
        center = create_center(code, tally=tally)
        create_station(center)
        result_form = create_result_form(form_state=FormState.UNSUBMITTED,
                                         center=center,
                                         tally=tally,
                                         station_number=station_number)
        request = self._get_request()
        view = views.CreateResultFormView.as_view()
        data = {'result_form': result_form.pk}
        request = self.factory.post('/', data=data)
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(
            request,
            form_id=result_form.pk,
            tally_id=tally.pk)
        self.assertEqual(response.status_code, 200)

    def test_edit_result_form_ballot_not_active_error(self):
        tally = create_tally()
        tally.users.add(self.user)
        code = '12345'
        ballot = create_ballot(tally=tally, active=False)
        sc, _ = SubConstituency.objects.get_or_create(code=1, field_office='1')
        center = create_center(code,
                               tally=tally,
                               sub_constituency=sc)
        station = create_station(center)
        form_data = {'center': center.pk,
                     'station_number': station.station_number,
                     'tally': tally.pk,
                     'form_state': 9,
                     'ballot': ballot.pk,
                     'barcode': 12345,
                     'gender': 1}
        form = EditResultForm(form_data)
        self.assertIn("Race for ballot is disabled", form.errors['__all__'])
        self.assertFalse(form.is_valid())

    def test_edit_result_form_center_not_active_error(self):
        tally = create_tally()
        tally.users.add(self.user)
        code = '12345'
        ballot = create_ballot(tally=tally)
        sc, _ = SubConstituency.objects.get_or_create(code=1, field_office='1')
        center = create_center(code,
                               tally=tally,
                               active=False,
                               sub_constituency=sc)
        station = create_station(center)
        form_data = {'center': center.pk,
                     'station_number': station.station_number,
                     'tally': tally.pk,
                     'form_state': 9,
                     'ballot': ballot.pk,
                     'barcode': 12345,
                     'gender': 1}
        form = EditResultForm(form_data)
        self.assertIn("Selected center is disabled", form.errors['__all__'])
        self.assertFalse(form.is_valid())

    def test_edit_result_form_barcode_exist_error(self):
        tally = create_tally()
        tally.users.add(self.user)
        code = '12345'
        ballot = create_ballot(tally=tally, number=2)
        sc, _ = SubConstituency.objects.get_or_create(code=1, field_office='1')
        center = create_center(code,
                               tally=tally,
                               sub_constituency=sc)
        station = create_station(center)
        form_data = {'center': center.pk,
                     'station_number': station.station_number,
                     'tally': tally.pk,
                     'form_state': 9,
                     'ballot': ballot.pk,
                     'barcode': 12345,
                     'gender': 1}
        form = EditResultForm(form_data)
        self.assertIn("Ballot number do not match for center and station",
                      form.errors['__all__'])
        self.assertFalse(form.is_valid())

    def test_edit_result_form_valid(self):
        tally = create_tally()
        tally.users.add(self.user)
        code = '12345'
        ballot = create_ballot(tally=tally)
        sc, _ = SubConstituency.objects.get_or_create(code=1, field_office='1')
        center = create_center(code,
                               tally=tally,
                               sub_constituency=sc)
        station = create_station(center)
        form_data = {'center': center.pk,
                     'station_number': station.station_number,
                     'tally': tally.pk,
                     'form_state': 9,
                     'ballot': ballot.pk,
                     'barcode': 12345,
                     'gender': 1}
        form = EditResultForm(form_data)
        self.assertTrue(form.is_valid())

    def test_remove_result_form_confirmation_get(self):
        tally = create_tally()
        tally.users.add(self.user)
        code = '12345'
        station_number = 1
        center = create_center(code, tally=tally)
        create_station(center)
        result_form = create_result_form(form_state=FormState.UNSUBMITTED,
                                         center=center,
                                         tally=tally,
                                         station_number=station_number)
        view = views.RemoveResultFormConfirmationView.as_view()
        request = self.factory.get('/')
        request.user = self.user
        response = view(
            request,
            form_id=result_form.pk,
            tally_id=tally.pk)
        self.assertContains(response, '<form name="remove-form-form"')

    def test_remove_result_form_confirmation_post(self):
        tally = create_tally()
        tally.users.add(self.user)
        code = '12345'
        station_number = 1
        center = create_center(code, tally=tally)
        create_station(center)
        result_form = create_result_form(form_state=FormState.UNSUBMITTED,
                                         center=center,
                                         tally=tally,
                                         station_number=station_number)
        view = views.RemoveResultFormConfirmationView.as_view()
        data = {'result_form': result_form.pk}
        request = self.factory.post('/', data=data)
        request.user = self.user
        request.session = {'result_form': result_form.pk}
        response = view(
            request,
            form_id=result_form.pk,
            tally_id=tally.pk)
        self.assertEqual(response.status_code, 302)

    def test_get_result_form_with_duplicate_results(self):
        tally = create_tally()
        tally.users.add(self.user)
        ballot_1 = create_ballot(tally=tally)
        barcode = '1234',
        center = create_center('12345', tally=tally)
        station = create_station(center)
        result_form_1 = create_result_form(
            tally=tally,
            ballot=ballot_1,
            center=center,
            station_number=station.station_number)
        result_form_2, _ = ResultForm.objects.get_or_create(
            id=2,
            ballot=ballot_1,
            barcode=barcode,
            serial_number=2,
            form_state=FormState.UNSUBMITTED,
            station_number=station.station_number,
            user=None,
            center=center,
            gender=Gender.MALE,
            is_replacement=False,
            tally=tally,
        )
        votes = 12
        create_candidates(result_form_1, votes=votes, user=self.user,
                          num_results=1)

        for result in result_form_1.results.all():
            result.entry_version = EntryVersion.FINAL
            result.save()
            # create duplicate final results
            create_result(result_form_2, result.candidate, self.user, votes)
        duplicate_results = views.get_result_form_with_duplicate_results(
            tally_id=tally.pk)
        self.assertIn(result_form_1, duplicate_results)
        self.assertIn(result_form_2, duplicate_results)

        # test filtering duplicate result forms by ballot
        ballot_2, _ = Ballot.objects.get_or_create(
            id=2,
            active=True,
            number=2,
            tally=tally,
            available_for_release=False,
            race_type=RaceType.GENERAL,
            document="")
        result_form_3, _ = ResultForm.objects.get_or_create(
            id=3,
            ballot=ballot_2,
            barcode="12345",
            serial_number=3,
            form_state=FormState.UNSUBMITTED,
            station_number=station.station_number,
            user=None,
            center=center,
            gender=Gender.MALE,
            is_replacement=False,
            tally=tally,
        )
        result_form_4, _ = ResultForm.objects.get_or_create(
            id=4,
            ballot=ballot_2,
            barcode="123456",
            serial_number=4,
            form_state=FormState.UNSUBMITTED,
            station_number=station.station_number,
            user=None,
            center=center,
            gender=Gender.MALE,
            is_replacement=False,
            tally=tally,
        )
        create_candidates(result_form_3, votes=votes, user=self.user,
                          num_results=1)

        for result in result_form_3.results.all():
            result.entry_version = EntryVersion.FINAL
            result.save()
            # create duplicate final results
            create_result(result_form_4, result.candidate, self.user, votes)
        ballot_1_duplicates = views.get_result_form_with_duplicate_results(
            ballot=ballot_1.pk,
            tally_id=tally.pk)
        ballot_2_duplicates = views.get_result_form_with_duplicate_results(
            ballot=ballot_2.pk,
            tally_id=tally.pk)
        all_duplicates = views.get_result_form_with_duplicate_results(
            tally_id=tally.pk)

        # check result_form_1 and result_form_2 are in ballot_1_duplicates
        self.assertIn(result_form_1, ballot_1_duplicates)
        self.assertIn(result_form_2, ballot_1_duplicates)

        # check result_form_3 and result_form_4 are not in ballot_1_duplicates
        self.assertNotIn(result_form_3, ballot_1_duplicates)
        self.assertNotIn(result_form_4, ballot_1_duplicates)

        # check result_form_3 and result_form_4 are in ballot_2_duplicates
        self.assertIn(result_form_3, ballot_2_duplicates)
        self.assertIn(result_form_4, ballot_2_duplicates)

        # check result_form_1 and result_form_2 are not in ballot_2_duplicates
        self.assertNotIn(result_form_1, ballot_2_duplicates)
        self.assertNotIn(result_form_2, ballot_2_duplicates)

        self.assertIn(result_form_1, all_duplicates)
        self.assertIn(result_form_2, all_duplicates)
        self.assertIn(result_form_3, all_duplicates)
        self.assertIn(result_form_4, all_duplicates)

    def test_duplicate_result_form_view_duplicate_reviewed_post(self):
        tally = create_tally()
        tally.users.add(self.user)
        ballot = create_ballot(tally=tally)
        barcode = '1234',
        center = create_center('12345', tally=tally)
        station = create_station(center)
        result_form_1 = create_result_form(
            tally=tally,
            ballot=ballot,
            center=center,
            station_number=station.station_number)
        result_form_2, _ = ResultForm.objects.get_or_create(
            id=2,
            ballot=ballot,
            barcode=barcode,
            serial_number=2,
            form_state=FormState.UNSUBMITTED,
            station_number=station.station_number,
            user=None,
            center=center,
            gender=Gender.MALE,
            is_replacement=False,
            tally=tally,
        )
        votes = 12
        create_candidates(result_form_1, votes=votes, user=self.user,
                          num_results=1)

        for result in result_form_1.results.all():
            result.entry_version = EntryVersion.FINAL
            result.save()
            # create duplicate final results
            create_result(result_form_2, result.candidate, self.user, votes)
        view = views.DuplicateResultFormView.as_view()
        data = {'duplicate_reviewed': 1}
        request = self.factory.post('/', data=data)
        request.user = self.user
        configure_messages(request)
        response = view(request, tally_id=tally.pk, ballot_id=ballot.pk)

        result_form_1.reload()
        result_form_2.reload()
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            "/super-administrator/duplicate-result-tracking",  response.url)
        self.assertTrue(result_form_1.duplicate_reviewed)
        self.assertTrue(result_form_2.duplicate_reviewed)

    def test_duplicate_result_form_view_send_clearance_post(self):
        tally = create_tally()
        tally.users.add(self.user)
        ballot = create_ballot(tally=tally)
        barcode = '1234',
        center = create_center('12345', tally=tally)
        station = create_station(center)
        result_form = create_result_form(
            tally=tally,
            ballot=ballot,
            barcode=barcode,
            center=center,
            station_number=station.station_number)
        votes = 12
        create_candidates(result_form, votes=votes, user=self.user,
                          num_results=1)
        view = views.DuplicateResultFormView.as_view()
        data = {'result_form': result_form.pk,
                'send_clearance': 1}
        request = self.factory.post('/', data=data)
        request.user = self.user
        configure_messages(request)
        request.session = {'result_form': result_form.pk}
        response = view(request, tally_id=tally.pk, ballot_id=ballot.pk)

        result_form.reload()
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            "/super-administrator/duplicate-result-tracking",  response.url)
        self.assertEqual(result_form.form_state, FormState.CLEARANCE)
        self.assertTrue(result_form.duplicate_reviewed)

        # check archived form is not sent to clearance
        result_form_2, _ = ResultForm.objects.get_or_create(
            id=2,
            ballot=ballot,
            barcode="1234",
            serial_number=2,
            form_state=FormState.ARCHIVED,
            station_number=station.station_number,
            user=None,
            center=center,
            gender=Gender.MALE,
            is_replacement=False,
            tally=tally,
        )
        create_candidates(result_form_2, votes=votes, user=self.user,
                          num_results=1)
        data = {'result_form': result_form_2.pk,
                'send_clearance': 1}
        request = self.factory.post('/', data=data)
        request.user = self.user
        configure_messages(request)
        request.session = {'result_form': result_form_2.pk}
        response = view(request, tally_id=tally.pk, ballot_id=ballot.pk)

        result_form_2.reload()
        self.assertNotEqual(result_form_2.form_state, FormState.CLEARANCE)
        self.assertEqual(result_form_2.form_state, FormState.ARCHIVED)
        self.assertEqual(response.status_code, 302)
        self.assertEqual("/",  response.url)

    def test_duplicate_result_form_view_send_all_clearance_post(self):
        tally = create_tally()
        tally.users.add(self.user)
        ballot = create_ballot(tally=tally)
        barcode = '1234',
        center = create_center('12345', tally=tally)
        station = create_station(center)
        result_form_1 = create_result_form(
            tally=tally,
            ballot=ballot,
            center=center,
            station_number=station.station_number)
        result_form_2, _ = ResultForm.objects.get_or_create(
            id=2,
            ballot=ballot,
            barcode=barcode,
            serial_number=2,
            form_state=FormState.UNSUBMITTED,
            station_number=station.station_number,
            user=None,
            center=center,
            gender=Gender.MALE,
            is_replacement=False,
            tally=tally,
        )
        votes = 12
        create_candidates(result_form_1, votes=votes, user=self.user,
                          num_results=1)

        for result in result_form_1.results.all():
            result.entry_version = EntryVersion.FINAL
            result.save()
            # create duplicate final results
            create_result(result_form_2, result.candidate, self.user, votes)
        view = views.DuplicateResultFormView.as_view()
        data = {'send_all_clearance': 1}
        request = self.factory.post('/', data=data)
        request.user = self.user
        configure_messages(request)
        response = view(request, tally_id=tally.pk, ballot_id=ballot.pk)

        result_form_1.reload()
        result_form_2.reload()
        self.assertEqual(response.status_code, 302)
        self.assertIn(
            "/super-administrator/duplicate-result-tracking",  response.url)
        self.assertEqual(result_form_1.form_state, FormState.CLEARANCE)
        self.assertTrue(result_form_1.duplicate_reviewed)
        self.assertEqual(result_form_2.form_state, FormState.CLEARANCE)
        self.assertTrue(result_form_2.duplicate_reviewed)

    def test_duplicate_archived_result_forms_send_all_clearance_post(self):
        tally = create_tally()
        tally.users.add(self.user)
        ballot = create_ballot(tally=tally)
        barcode = '1234',
        center = create_center('12345', tally=tally)
        station = create_station(center)
        result_form_1 = create_result_form(
            tally=tally,
            ballot=ballot,
            center=center,
            station_number=station.station_number)
        result_form_2, _ = ResultForm.objects.get_or_create(
            id=2,
            ballot=ballot,
            barcode=barcode,
            serial_number=2,
            form_state=FormState.ARCHIVED,
            station_number=station.station_number,
            user=None,
            center=center,
            gender=Gender.MALE,
            is_replacement=False,
            tally=tally,
        )
        votes = 12
        create_candidates(result_form_1, votes=votes, user=self.user,
                          num_results=1)
        for result in result_form_1.results.all():
            result.entry_version = EntryVersion.FINAL
            result.save()
            # create duplicate final results
            create_result(result_form_2, result.candidate, self.user, votes)
        view = views.DuplicateResultFormView.as_view()
        data = {'send_all_clearance': 1}
        request = self.factory.post('/', data=data)
        request.user = self.user
        configure_messages(request)
        response = view(request, tally_id=tally.pk, ballot_id=ballot.pk)

        result_form_1.reload()
        result_form_2.reload()
        self.assertEqual(response.status_code, 302)
        self.assertEqual("/", response.url)
        self.assertEqual(result_form_1.form_state, FormState.CLEARANCE)
        self.assertTrue(result_form_1.duplicate_reviewed)
        self.assertNotEqual(result_form_2.form_state, FormState.CLEARANCE)
        self.assertFalse(result_form_2.duplicate_reviewed)
