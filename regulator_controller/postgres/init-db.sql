--таблица зарегистрированных учреждений
CREATE TABLE IF NOT EXISTS public."REGISTERED_INSTITUTIONS"
(
    institution_did integer NOT NULL,
    institution_type character varying COLLATE pg_catalog."default" NOT NULL,
    institution_name character varying COLLATE pg_catalog."default",
    connection_id character varying COLLATE pg_catalog."default",
    registration_date date,
    CONSTRAINT "REGISTERED_INSTITUTIONS_pkey" PRIMARY KEY (institution_did)
);

--таблица разрешённых типов документов
CREATE TABLE IF NOT EXISTS public."APPROVED_CREDENTIALS"
(
    vc_type integer NOT NULL,
    vc_name character varying COLLATE pg_catalog."default",
    vc_short_name character varying COLLATE pg_catalog."default",
    registration_date date NOT NULL,
    CONSTRAINT "APPROVED_CREDENTIALS_pkey" PRIMARY KEY (vc_type)
);

--таблица связки 'учреждение'<->'типы документов разрешённые для выпуска'
CREATE TABLE IF NOT EXISTS public."CREDENTIAL_INSTITUTION_APPROVE"
(
    institution_did integer NOT NULL,
    vc_type integer NOT NULL,
    date_approve date NOT NULL,
    CONSTRAINT "CREDENTIAL_INSTITUTION_APPROVE_pkey" PRIMARY KEY (institution_did, vc_type, date_approve),
    CONSTRAINT "INSTITUTION_CREDINTIAL_DID" FOREIGN KEY (institution_did)
        REFERENCES public."REGISTERED_INSTITUTIONS" (institution_did) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE SET NULL,
    CONSTRAINT "INSTITUTION_CREDINTIAL_VC_TYPE" FOREIGN KEY (vc_type)
        REFERENCES public."APPROVED_CREDENTIALS" (vc_type) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE SET NULL
);

--таблица заявок учреждений на разрешение выпуска нового типа документа'
CREATE TABLE IF NOT EXISTS public."CREDENTIAL_ISSUANCE_REQUESTS"
(
    request_id character varying NOT NULL,
    institution_did integer NOT NULL,
    vc_type integer NOT NULL,
    request_date date NOT NULL,
    reject_date date,
    approved_date date,
    CONSTRAINT "CREDENTIAL_ISSUANCE_REQUESTS_pkey" PRIMARY KEY (request_id),
    CONSTRAINT "INSTITUTION_CREDINTIAL_REQUESTS_DID" FOREIGN KEY (institution_did)
        REFERENCES public."REGISTERED_INSTITUTIONS" (institution_did) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE SET NULL,
    CONSTRAINT "INSTITUTION_CREDINTIAL_REQUESTS_VC_TYPE" FOREIGN KEY (vc_type)
        REFERENCES public."APPROVED_CREDENTIALS" (vc_type) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE SET NULL
)

