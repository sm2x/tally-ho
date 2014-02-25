from django.conf.urls import patterns, include, url

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView

from libya_tally.apps.tally.forms.login_form import LoginForm
from libya_tally.apps.tally.forms.password_change import PasswordChangeForm
from libya_tally.apps.tally.views import archive, audit, clearance,\
    corrections, data_entry_clerk, home, intake, quality_control,\
    super_admin, profile
from libya_tally.apps.tally.views.reports import offices
from libya_tally.apps.tally.views.reports import races

admin.autodiscover()

accounts_urls = patterns(
    '',
    url(r'^login/$',
        profile.login,
        {
            'template_name': 'registration/login.html',
            'authentication_form': LoginForm
        },
        name='login'),
    url(r'^password_change/$',
        'django.contrib.auth.views.password_change',
        {
            'password_change_form': PasswordChangeForm,
            'post_change_redirect': '/'},
        name='password_change'),
    url(r'^password_change/done/$',
        'django.contrib.auth.views.password_change_done',
        name='password_change_done'),
    url(r'^logout/$', auth_views.logout, {'next_page': '/'}, name='logout'),
)

handler403 = 'libya_tally.apps.tally.views.home.permission_denied'
handler404 = 'libya_tally.apps.tally.views.home.not_found'
handler400 = 'libya_tally.apps.tally.views.home.bad_request'
handler500 = 'libya_tally.apps.tally.views.home.server_error'

urlpatterns = patterns(
    '',
    url(r'^$', home.HomeView.as_view(), name='home'),
    url(r'^locale$', home.LocaleView.as_view(), name='home-locale'),

    url(r'^super-administrator$',
        super_admin.DashboardView.as_view(), name='super-administrator'),
    url(r'^super-administrator/center-list$',
        super_admin.CenterListView.as_view(),
        name='center-list'),
    url(r'^super-administrator/center-list-data$',
        super_admin.CenterListDataView.as_view(),
        name='center-list-data'),
    url(r'^super-administrator/form-list$',
        super_admin.FormListView.as_view(),
        name='form-list'),
    url(r'^super-administrator/form-list/(?P<state>.*)/$',
        super_admin.FormListView.as_view(),
        name='form-list'),
    url(r'^super-administrator/form-list-data$',
        super_admin.FormListDataView.as_view(),
        name='form-list-data'),
    url(r'^super-administrator/form-progress$',
        super_admin.FormProgressView.as_view(),
        name='form-progress'),
    url(r'^super-administrator/form-duplicates$',
        super_admin.FormDuplicatesView.as_view(),
        name='form-duplicates'),
    url(r'^super-administrator/form-action-list$',
        super_admin.FormActionView.as_view(),
        name='form-action-view'),
    url(r'^super-administrator/form-progress-data$',
        super_admin.FormProgressDataView.as_view(),
        name='form-progress-data'),
    url(r'^super-administrator/form-duplicates-data$',
        super_admin.FormDuplicatesDataView.as_view(),
        name='form-duplicates-data'),
    url(r'^super-administrator/form-not-received.(?P<format>(csv))$',
        super_admin.FormNotReceivedListView.as_view(),
        name='form-not-received-view'),
    url(r'^super-administrator/form-not-received$',
        super_admin.FormNotReceivedListView.as_view(),
        name='form-not-received-view'),
    url(r'^super-administrator/results-(?P<report>(formlist|candidate))$',
        super_admin.ResultExportView.as_view(),
        name='result-export'),
    url(r'^super-administrator/results$',
        super_admin.ResultExportView.as_view(),
        name='result-export'),
    url(r'^super-administrator/form-not-received-data$',
        super_admin.FormNotReceivedDataView.as_view(),
        name='form-not-received-data'),

    url(r'^data-entry$', data_entry_clerk.DataEntryView.as_view(),
        name='data-entry-clerk'),
    url(r'^data-entry/enter-center-details$',
        data_entry_clerk.CenterDetailsView.as_view(),
        name='data-entry-enter-center-details'),
    url(r'^data-entry/enter-results',
        data_entry_clerk.EnterResultsView.as_view(),
        name='enter-results'),
    url(r'^data-entry/success',
        data_entry_clerk.ConfirmationView.as_view(),
        name='data-entry-success'),

    url(r'^intake/center-details$', intake.CenterDetailsView.as_view(),
        name='intake'),
    url(r'^intake/enter-center', intake.EnterCenterView.as_view(),
        name='intake-enter-center'),
    url(r'^intake/check-center-details$',
        intake.CheckCenterDetailsView.as_view(),
        name='check-center-details'),
    url(r'^intake/printcover$',
        intake.PrintCoverView.as_view(),
        name='intake-printcover'),
    url(r'^intake/clearance$',
        intake.ClearanceView.as_view(),
        name='intake-clearance'),
    url(r'^intake/intaken',
        intake.ConfirmationView.as_view(),
        name='intaken'),

    url(r'^quality-control/home$',
        quality_control.QualityControlView.as_view(),
        name='quality-control-clerk'),
    url(r'^quality-control/dashboard$',
        quality_control.QualityControlDashboardView.as_view(),
        name='quality-control-dashboard'),
    url(r'^quality-control/reject$',
        TemplateView.as_view(
            template_name='tally/quality_control/reject.html'),
        name='quality-control-reject'),
    url(r'^quality-control/success$',
        quality_control.ConfirmationView.as_view(),
        name='quality-control-success'),

    url(r'^corrections$',
        corrections.CorrectionView.as_view(),
        name='corrections-clerk'),
    url(r'^corrections/match$',
        corrections.CorrectionMatchView.as_view(),
        name='corrections-match'),
    url(r'^corrections/required$',
        corrections.CorrectionRequiredView.as_view(),
        name='corrections-required'),
    url(r'^corrections/success$',
        corrections.ConfirmationView.as_view(),
        name='corrections-success'),

    url(r'^archive$',
        archive.ArchiveView.as_view(),
        name='archive'),
    url(r'^archive/print$',
        archive.ArchivePrintView.as_view(),
        name='archive-print'),
    url(r'^archive/success$',
        archive.ConfirmationView.as_view(),
        name='archive-success'),

    url(r'^audit$',
        audit.DashboardView.as_view(),
        name='audit'),
    url(r'^audit/new',
        audit.CreateAuditView.as_view(),
        name='audit-new'),
    url(r'^audit/print',
        audit.PrintCoverView.as_view(),
        name='audit-print'),
    url(r'^audit/review$',
        audit.ReviewView.as_view(),
        name='audit-review'),

    url(r'^clearance$',
        clearance.DashboardView.as_view(),
        name='clearance'),
    url(r'^clearance/new',
        clearance.NewFormView.as_view(),
        name='clearance-new'),
    url(r'^clearance/print',
        clearance.PrintCoverView.as_view(),
        name='clearance-print'),
    url(r'^clearance/review$',
        clearance.ReviewView.as_view(),
        name='clearance-review'),
    url(r'^clearance/create',
        clearance.CreateClearanceView.as_view(),
        name='clearance-create'),

    url(r'^reports/internal/offices',
        offices.OfficesReportView.as_view(),
        name='reports-offices'),
    url(r'^reports/internal/race',
        races.RacesReportView.as_view(),
        name='reports-races'),

    url(r'^operation-not-allowed',
        home.suspicious_error, name='suspicious-error'),

    url(r'^accounts/', include(accounts_urls)),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^tracking/', include('tracking.urls')),
    url(r'^djangojs/', include('djangojs.urls')),
)
