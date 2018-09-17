from lxml import etree
from scibot.utils import DOI, PMID


def annotate_doi_pmid(target_uri, doi, pmid, h, tags):  # TODO
    # need to check for existing ...
    doi_ = 'DOI:' + doi
    text_list = []
    tags_to_add = []
    if doi_ not in tags:
        text_list.append(DOI(doi))
        tags_to_add.append(doi_)
    if pmid and pmid not in tags:
        text_list.append(PMID(pmid))
        tags_to_add.append(pmid)
    if tags_to_add:
        r = h.create_annotation_with_target_using_only_text_quote(target_uri,
                                                                  text='\n'.join(text_list),
                                                                  tags=tags_to_add)
        print(r)
        print(r.text)
        return r


def submit_to_h(target_uri, found, resolved, h, found_rrids, existing):
    prefix, exact, exact_for_hypothesis, suffix = found
    xml, status_code, resolver_uri = resolved

    new_tags = []
    if exact in existing:
        new_tags.append('RRIDCUR:Duplicate')
    else:
        existing.append(exact)

    if status_code < 300:
        root = etree.fromstring(xml)
        if root.findall('error'):
            s = 'Resolver lookup failed.'
            s += '<hr><p><a href="%s">resolver lookup</a></p>' % resolver_uri
            r = h.create_annotation_with_target_using_only_text_quote(url=target_uri, prefix=prefix, exact=exact_for_hypothesis, suffix=suffix, text=s, tags=new_tags + ['RRIDCUR:Unresolved'])
            print('ERROR, rrid unresolved')
        else:
            s = ''
            title = root.findall('title')[0].text
            s += f'Title: {title}\n'
            data_elements = root.findall('data')[0]
            data_elements = [(e.find('name').text, e.find('value').text) for e in data_elements]  # these shouldn't duplicate
            citation = [(n, v) for n, v in  data_elements if n == 'Proper Citation']
            name = [(n, v) for n, v in  data_elements if n == 'Name']
            data_elements = citation + name + sorted([(n, v) for n, v in  data_elements if (n != 'Proper Citation' or n != 'Name') and v is not None])
            for name, value in data_elements:
                if (name == 'Reference' or name == 'Mentioned In Literature') and value is not None and value.startswith('<a class'):
                    if len(value) > 500:
                        continue  # nif-0000-30467 fix keep those pubmed links short!
                s += '<p>%s: %s</p>' % (name, value)
            s += '<hr><p><a href="%s">resolver lookup</a></p>' % resolver_uri
            r = h.create_annotation_with_target_using_only_text_quote(url=target_uri, prefix=prefix, exact=exact_for_hypothesis, suffix=suffix, text=s, tags=new_tags + [exact])
    elif status_code >= 500:
        s = 'Resolver lookup failed due to server error.'
        s += '<hr><p><a href="%s">resolver lookup</a></p>' % resolver_uri
    else:
        s = 'Resolver lookup failed.'
        s += '<hr><p><a href="%s">resolver lookup</a></p>' % resolver_uri
        r = h.create_annotation_with_target_using_only_text_quote(url=target_uri,
                                                                  prefix=prefix,
                                                                  exact=exact_for_hypothesis,
                                                                  suffix=suffix,
                                                                  text=s,
                                                                  tags=new_tags + ['RRIDCUR:Unresolved'])
    found_rrids[exact] = r.json()['links']['incontext']
    return r
