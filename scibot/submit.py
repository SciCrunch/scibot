from lxml import etree
from scibot.utils import DOI, PMID, rrid_from_citation, log

def make_extra(document, expanded_exact=None):
    out = {'document': document,}
    if expanded_exact:
        out['expanded_exact'] = expanded_exact

    return out

def annotate_doi_pmid(target_uri, document, doi, pmid, h, tags, extra_text=None):  # TODO
    # need to check for existing ...
    extra = make_extra(document)
    text_list = []
    tags_to_add = []
    if extra_text is not None:
        text_list.append(extra_text)
    if doi is not None:
        doi_ = 'DOI:' + doi
        if doi_ not in tags:
            text_list.append(DOI(doi))
            tags_to_add.append(doi_)
    if pmid and pmid not in tags:
        text_list.append(PMID(pmid))
        tags_to_add.append(pmid)
    if tags_to_add:
        r = h.create_annotation_with_target_using_only_text_quote(url=target_uri,
                                                                  document=document,
                                                                  text='\n'.join(text_list),
                                                                  tags=tags_to_add,
                                                                  extra=extra,)
        log.info(r)
        log.info(r.text)
        return r


def submit_to_h(target_uri, document, found, resolved, h, found_rrids, existing, existing_with_suffixes):
    prefix, exact, exact_for_hypothesis, suffix = found
    xml, status_code, resolver_uri = resolved
    extra = make_extra(document, exact)

    if exact.startswith('RRID:'):
        tail = exact[len('RRID:'):]
    else:
        tail = exact

    duplicate = exact in existing
    suffix_match = (tail, suffix) in existing_with_suffixes  # FIXME prefix tree for fuzzier matches
    new_tags = []
    if duplicate:
        new_tags.append('RRIDCUR:Duplicate')
    elif suffix_match:
        log.info(f'suffix matches, skipping entirely, {tail} {suffix}')
        return
    else:
        # note that we use the normalized exact here to detect
        # duplicates but provide the canonical RRID: as the tag
        existing.append(exact)
        existing_with_suffixes.append((tail, suffix))

    if status_code < 300:
        root = etree.fromstring(xml)
        if duplicate:
            # just mark the duplicate so that it will anchor in the client
            # but don't add the RRID: tag and don't include the resolver metadata
            r = h.create_annotation_with_target_using_only_text_quote(url=target_uri,
                                                                      document=document,
                                                                      prefix=prefix,
                                                                      exact=exact_for_hypothesis,
                                                                      suffix=suffix,
                                                                      text='',
                                                                      tags=new_tags,
                                                                      extra=extra,)

        elif root.findall('error'):
            s = 'Resolver lookup failed.'
            s += '<hr><p><a href="%s">resolver lookup</a></p>' % resolver_uri
            r = h.create_annotation_with_target_using_only_text_quote(url=target_uri,
                                                                      document=document,
                                                                      prefix=prefix,
                                                                      exact=exact_for_hypothesis,
                                                                      suffix=suffix,
                                                                      text=s,
                                                                      tags=new_tags + ['RRIDCUR:Unresolved'],
                                                                      extra=extra,)
            log.error(f'rrid unresolved {exact}')

        else:
            s = ''
            title = root.findall('title')[0].text
            s += f'Title: {title}\n'
            data_elements = root.findall('data')[0]
            data_elements = [(e.find('name').text, e.find('value').text) for e in data_elements]  # these shouldn't duplicate
            citation = [(n, v) for n, v in  data_elements if n == 'Proper Citation']
            rrid = [rrid_from_citation(c) for _, c in citation] if citation else [exact]
            name = [(n, v) for n, v in  data_elements if n == 'Name']
            data_elements = citation + name + sorted([(n, v) for n, v in 
                                                      data_elements if (n != 'Proper Citation' or
                                                                        n != 'Name') and v is not None])
            for name, value in data_elements:
                if ((name == 'Reference' or name == 'Mentioned In Literature')
                    and value is not None and value.startswith('<a class')):
                    if len(value) > 500:
                        continue  # nif-0000-30467 fix keep those pubmed links short!
                s += '<p>%s: %s</p>' % (name, value)
            s += '<hr><p><a href="%s">resolver lookup</a></p>' % resolver_uri
            r = h.create_annotation_with_target_using_only_text_quote(url=target_uri,
                                                                      document=document,
                                                                      prefix=prefix,
                                                                      exact=exact_for_hypothesis,
                                                                      suffix=suffix,
                                                                      text=s,
                                                                      tags=new_tags + rrid,
                                                                      extra=extra,)

    elif status_code >= 500:
        s = 'Resolver lookup failed due to server error.'
        s += '<hr><p><a href="%s">resolver lookup</a></p>' % resolver_uri
        r = None
        log.error(f'{status_code} error for {resolver_uri}')
    else:
        s = 'Resolver lookup failed.'
        s += '<hr><p><a href="%s">resolver lookup</a></p>' % resolver_uri
        r = h.create_annotation_with_target_using_only_text_quote(url=target_uri,
                                                                  document=document,
                                                                  prefix=prefix,
                                                                  exact=exact_for_hypothesis,
                                                                  suffix=suffix,
                                                                  text=s,
                                                                  tags=new_tags + ['RRIDCUR:Unresolved'],
                                                                  extra=extra,)
    if r is not None:
        found_rrids[exact] = r.json()['links']['incontext']

    return r

def api_row_to_db(api_row):
    # TODO insert the created annotation into our local store
    # check for contention/consistency with the websocket
    pass
