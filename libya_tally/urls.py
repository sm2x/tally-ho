from django.conf.urls import patterns, include, url

from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView

from libya_tally.apps.tally.views import archive, clearance, corrections,\
    data_entry_clerk, home, intake_clerk, quality_control, super_admin

admin.autodiscover()

accounts_urls = patterns(
    '',
    url(r'^login/$', auth_views.login,
        {'template_name': 'registration/login.html'},
        name='login'),
    url(r'^logout/$', auth_views.logout, {'next_page': '/'}, name='logout'),
)

urlpatterns = patterns(
    '',
    url(r'^$', home.HomeView.as_view(), name='home'),

    url(r'^super-administrator$',
        super_admin.DashboardView.as_view(), name='super-administrator'),
    url(r'^super-administrator/center-list$',
        super_admin.CenterListView.as_view(),
        name='center-list'),
    url(r'^super-administrator/form-list$',
        super_admin.FormListView.as_view(),
        name='form-list'),
    url(r'^super-administrator/form-progress',
        super_admin.FormProgressView.as_view(),
        name='form-progress'),

    url(r'^data-entry$', data_entry_clerk.DataEntryView.as_view(),
        name='data-entry-clerk'),
    url(r'^data-entry/enter-center-details$',
        data_entry_clerk.CenterDetailsView.as_view(),
        name='data-entry-enter-center-details'),
    url(r'^data-entry/check-center-details$',
        data_entry_clerk.CheckCenterDetailsView.as_view(),
        name='data-entry-check-center-details'),
    url(r'^data-entry/enter-results',
        data_entry_clerk.EnterResultsView.as_view(),
        name='enter-results'),

    url(r'^intake/center-details$', intake_clerk.CenterDetailsView.as_view(),
        name='intake-clerk'),
    url(r'^intake/enter-center', intake_clerk.EnterCenterView.as_view(),
        name='intake-enter-center'),
    url(r'^intake/check-center-details$',
        intake_clerk.CheckCenterDetailsView.as_view(),
        name='check-center-details'),
    url(r'^intake/printcover$',
        intake_clerk.PrintCoverView.as_view(),
        name='intake-printcover'),
    url(r'^intake/clearance$',
        intake_clerk.ClearanceView.as_view(),
        name='intake-clearance'),
    url(r'^intake/intaken',
        TemplateView.as_view(template_name='tally/intake/success.html'),
        name='intaken'),

    url(r'^quality-control/home$',
        quality_control.QualityControlView.as_view(),
        name='quality-control-clerk'),
    url(r'^quality-control/dashboard$',
        quality_control.QualityControlDashboardView.as_view(),
        name='quality-control-dashboard'),
    url(r'^quality-control/reject',
        TemplateView.as_view(
            template_name='tally/quality-control/reject.html'),
        name='quality-control-reject'),
    url(r'^quality-control/reconciliation',
        quality_control.QualityControlReconciliationView.as_view(),
        name='quality-control-reconciliation'),
    url(r'^quality-control/general',
        quality_control.QualityControlGeneralView.as_view(),
        name='quality-control-general'),
    url(r'^quality-control/women',
        quality_control.QualityControlWomenView.as_view(),
        name='quality-control-women'),

    url(r'^corrections$',
        corrections.CorrectionView.as_view(),
        name='corrections-clerk'),
    url(r'^corrections/dashboard$',
        corrections.CorrectionDashboardView.as_view(),
        name='corrections-dashboard'),
    url(r'^corrections/match$',
        corrections.CorrectionMatchView.as_view(),
        name='corrections-match'),
    url(r'^corrections/general$',
        corrections.CorrectionGeneralView.as_view(),
        name='corrections-general'),
    url(r'^corrections/women$',
        corrections.CorrectionWomenView.as_view(),
        name='corrections-women'),
    url(r'^corrections/reconciliation$',
        corrections.CorrectionReconciliationView.as_view(),
        name='corrections-reconciliation'),

    url(r'^archive',
        archive.ArchiveView.as_view(),
        name='archive-clerk'),
    url(r'^archive/print',
        archive.ArchiveView.as_view(),
        name='archive-print'),

    url(r'^clearance',
        clearance.ClearanceDashboardView.as_view(),
        name='clearance-clerk'),
    url(r'^cwclearance/review',
        clearance.ClearanceReviewView.as_view(),
        name='clearance-review'),

    url(r'^accounts/', include(accounts_urls)),
    url(r'^admin/', include(admin.site.urls)),
)
