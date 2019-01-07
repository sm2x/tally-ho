from django import forms
from django.utils.translation import ugettext_lazy as _

from tally_ho.apps.tally.models.center import Center
from tally_ho.apps.tally.models.station import Station
from tally_ho.apps.tally.models.ballot import Ballot
from tally_ho.libs.models.enums.disable_reason import DisableReason
from tally_ho.libs.utils.active_status import (
    disable_enable_entity,
    disable_enable_race,
)


class DisableEntityForm(forms.Form):
    disable_reason = forms.TypedChoiceField(
        choices=DisableReason.choices(),
        error_messages={'invalid': _(u"Expecting one option selected")},
        widget=forms.RadioSelect(
            attrs={'class': '', 'autofocus': 'on'}),
        label=_(u"Select a reason"),
        coerce=int,
        empty_value=None,
    )

    comment_input = forms.CharField(
        required=False,
        label=_("Comments"),
        widget=forms.Textarea(attrs={'cols': 80, 'rows': 5}),
    )

    tally_id = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )

    center_code_input = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )

    station_number_input = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )

    race_id_input = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )

    def clean(self):
        if self.is_valid():
            cleaned_data = super(DisableEntityForm, self).clean()
            tally_id = cleaned_data.get('tally_id')
            center_code = cleaned_data.get('center_code_input')
            station_number = cleaned_data.get('station_number_input')
            race_id = cleaned_data.get('race_id_input')

            if center_code:
                try:
                    if station_number:
                        Station.objects.get(
                            station_number=station_number,
                            center__code=center_code,
                            center__tally__id=tally_id)
                    else:
                        Center.objects.get(tally__id=tally_id,
                                           code=center_code)
                except Center.DoesNotExist:
                    raise forms.ValidationError(
                        u"Center Number does not exist")
                except Station.DoesNotExist:
                    raise forms.ValidationError(
                        u"Station Number does not exist")
            elif race_id:
                try:
                    Ballot.objects.get(id=race_id)
                except Ballot.DoesNotExist:
                    raise forms.ValidationError(u"Race does not exist")
            else:
                raise forms.ValidationError(u"Error")

            return cleaned_data

    def save(self):
        if self.is_valid():
            tally_id = self.cleaned_data.get('tally_id')
            center_code = self.cleaned_data.get('center_code_input')
            station_number = self.cleaned_data.get('station_number_input')
            race_id = self.cleaned_data.get('race_id_input')
            disable_reason = self.cleaned_data.get('disable_reason')
            comment = self.cleaned_data.get('comment_input')

            result = None

            if not race_id:
                result = disable_enable_entity(center_code,
                                               station_number,
                                               disable_reason,
                                               comment,
                                               tally_id)
            else:
                result = disable_enable_race(race_id,
                                             disable_reason,
                                             comment,
                                             tally_id)

            return result