#!/usr/bin/env python
# vim: set encoding=utf-8


from django.contrib import admin
from django import forms
from django.forms.models import BaseInlineFormSet
from django.contrib.admin.widgets import FilteredSelectMultiple

from webtriathlon.misc import shift

from webtriathlon.core.models import *

class StageInline(admin.TabularInline):
    #inlines = [VariantInline] #Not supported in django yet
    #form = StageForm
    model = Stage
    extra = 3

admin.site.register(Category)
admin.site.register(SubCategory)
admin.site.register(LapType)

class PassageFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super(PassageFormSet, self).__init__(*args, **kwargs)
        self.can_delete = False

class PassageInline(admin.TabularInline):
    model = Passage
    formset = PassageFormSet
    list_per_page = 5
    extra = 3
    readonly_fields = ("duplicate",)

class PassageAdmin(admin.ModelAdmin):
    model = Passage
    save_as = True
    save_on_top = True
    readonly_fields = ("duplicate",)

class StationAdmin(admin.ModelAdmin):
    model = Station
    extra = 1


class PathAdmin(admin.ModelAdmin):
    model = Path
    inlines = [StageInline]

admin.site.register(Path, PathAdmin)

class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        widgets = {
                'members': FilteredSelectMultiple('Membres', is_stacked=False,
                    attrs={"size":"8", "style": "height: 150px"})
        }

    def clean_path(self):
        data = self.cleaned_data
        if "category" not in self.cleaned_data:
            return self.cleaned_data
        category = data["category"]
        if not data["path"]:
            try:
                data["path"] = get_default_path(category)
            except ValueError:
                raise forms.ValidationError("Veuillez créer un parcours pour cette catégorie")
        path = data["path"]
        if not path.categories.filter(id=category.id).count():
            raise forms.ValidationError("Ce parcours n'est pas authorisé dans cette "
                "catégorie")
        for l_v, v in shift(path):
            if l_v.after: l_s = l_v.after.station
            else: l_s = l_v.main_station
            if v.before: v_s = v.before.station
            else: v_s = v.main_station
            if l_s != v_s:
                raise forms.ValidationError(
                        "Les postes ne correspondent pas entre %s et %s"%(l_v,
                            v))
        return path

class TeamAdmin(admin.ModelAdmin):
    model = Team
    form = TeamForm
    inlines = [PassageInline]
    extra = 5
    list_display = ("nb", "category", "get_subcats", "path", "get_members")
    fields = ("nb", "category", "subcategories", "path", "members",
            "disqualified", "_have_finished", "_checked")
    search_fields = ("nb",)
    save_on_top = True

    def get_subcats(self, obj):
        return " ".join(map(str, obj.subcategories.all()))
    get_subcats.short_description = "Sous Catégories"

    def get_members(self, obj):
        return ", ".join(map(str, obj.members.all()))
    get_members.short_description = "Membres"

admin.site.register(Station, StationAdmin)
admin.site.register(Team, TeamAdmin)
admin.site.register(Passage, PassageAdmin)
admin.site.register(Junction)
from django.contrib import admin

from models import *

admin.site.register(Person)
