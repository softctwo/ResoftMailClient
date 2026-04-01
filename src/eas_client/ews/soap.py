SOAP_ENVELOPE_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:m="http://schemas.microsoft.com/exchange/services/2006/messages"
               xmlns:t="http://schemas.microsoft.com/exchange/services/2006/types"
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
{body}
  </soap:Body>
</soap:Envelope>
"""


def build_find_item_envelope(max_entries: int = 10) -> str:
    body = f"""    <m:FindItem Traversal="Shallow">
      <m:ItemShape>
        <t:BaseShape>IdOnly</t:BaseShape>
        <t:AdditionalProperties>
          <t:FieldURI FieldURI="item:Subject"/>
          <t:FieldURI FieldURI="item:DateTimeReceived"/>
          <t:FieldURI FieldURI="message:From"/>
          <t:FieldURI FieldURI="message:HasAttachments"/>
        </t:AdditionalProperties>
      </m:ItemShape>
      <m:IndexedPageItemView MaxEntriesReturned="{max_entries}" Offset="0" BasePoint="Beginning"/>
      <m:ParentFolderIds>
        <t:DistinguishedFolderId Id="inbox"/>
      </m:ParentFolderIds>
    </m:FindItem>"""
    return SOAP_ENVELOPE_TEMPLATE.format(body=body)


def build_get_item_envelope(item_id: str) -> str:
    body = f"""    <m:GetItem>
      <m:ItemShape>
        <t:BaseShape>IdOnly</t:BaseShape>
        <t:AdditionalProperties>
          <t:FieldURI FieldURI="item:Subject"/>
          <t:FieldURI FieldURI="item:Body"/>
          <t:FieldURI FieldURI="item:Attachments"/>
        </t:AdditionalProperties>
      </m:ItemShape>
      <m:ItemIds>
        <t:ItemId Id="{_xml_escape(item_id)}"/>
      </m:ItemIds>
    </m:GetItem>"""
    return SOAP_ENVELOPE_TEMPLATE.format(body=body)


def build_get_attachment_envelope(attachment_id: str) -> str:
    body = f"""    <m:GetAttachment>
      <m:AttachmentShape>
        <t:IncludeMimeContent>false</t:IncludeMimeContent>
      </m:AttachmentShape>
      <m:AttachmentIds>
        <t:AttachmentId Id="{_xml_escape(attachment_id)}"/>
      </m:AttachmentIds>
    </m:GetAttachment>"""
    return SOAP_ENVELOPE_TEMPLATE.format(body=body)


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
