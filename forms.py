from wtforms import Form, StringField, SelectField
 
class SearchForm(Form):
    choices = [('ID', 'ID'),
               ('Tags', 'Tags'),
               ('Organism', 'Organism'),
               ('Antibody ID','Antibody ID'),
               ('Proper Citation','Proper Citation'),
               ('Cat Num','Cat Num'),
               ('Clonality','Clonality'),
               ('Target Antigen','Target Antigen'),
               ('Vendor','Vendor'),
               ('Category','Category'),
               ('User','User')]
    select = SelectField('Search for annotations:', choices=choices)
    search = StringField('')
